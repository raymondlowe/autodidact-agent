"""
Database module for Autodidact
Handles SQLite database operations with direct SQL (no ORM)
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from contextlib import contextmanager

# Constants
MASTERY_THRESHOLD = 0.7
DB_PATH = Path.home() / '.autodidact' / 'autodidact.db'


def ensure_db_directory():
    """Ensure the database directory exists with proper permissions"""
    db_dir = DB_PATH.parent
    db_dir.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to 700 (rwx------)
    db_dir.chmod(0o700)


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    ensure_db_directory()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize the database with the schema"""
    schema = """
    CREATE TABLE IF NOT EXISTS project (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        report_path TEXT,
        graph_json TEXT,
        footnotes_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS node (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        original_id TEXT,
        label TEXT NOT NULL,
        summary TEXT,
        mastery REAL DEFAULT 0.0,
        FOREIGN KEY (project_id) REFERENCES project(id)
    );

    CREATE TABLE IF NOT EXISTS edge (
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        project_id TEXT NOT NULL,
        confidence REAL,
        rationale TEXT,
        FOREIGN KEY (project_id) REFERENCES project(id),
        PRIMARY KEY (project_id, source, target)
    );

    CREATE TABLE IF NOT EXISTS learning_objective (
        id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL,
        description TEXT NOT NULL,
        mastery REAL DEFAULT 0.0,
        FOREIGN KEY (node_id) REFERENCES node(id)
    );

    CREATE TABLE IF NOT EXISTS session (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        node_id TEXT NOT NULL,
        session_number INTEGER NOT NULL,
        status TEXT DEFAULT 'in_progress',
        final_score REAL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES project(id),
        FOREIGN KEY (node_id) REFERENCES node(id)
    );

    CREATE TABLE IF NOT EXISTS transcript (
        session_id TEXT NOT NULL,
        turn_idx INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (session_id, turn_idx),
        FOREIGN KEY (session_id) REFERENCES session(id)
    );
    
    -- Create indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_node_project ON node(project_id);
    CREATE INDEX IF NOT EXISTS idx_node_original ON node(original_id);
    CREATE INDEX IF NOT EXISTS idx_edge_project ON edge(project_id);
    CREATE INDEX IF NOT EXISTS idx_lo_node ON learning_objective(node_id);
    CREATE INDEX IF NOT EXISTS idx_session_project ON session(project_id);
    CREATE INDEX IF NOT EXISTS idx_session_node ON session(node_id);
    CREATE INDEX IF NOT EXISTS idx_transcript_session ON transcript(session_id);
    """
    
    with get_db_connection() as conn:
        conn.executescript(schema)
        conn.commit()


def create_project(topic: str, report_path: str, graph_json: Dict, footnotes: Dict) -> str:
    """Create a new project and return its ID"""
    project_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                INSERT INTO project (id, topic, report_path, graph_json, footnotes_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                project_id,
                topic,
                report_path,
                json.dumps(graph_json),
                json.dumps(footnotes)
            ))
            conn.commit()
            return project_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to create project: {str(e)}")


def save_graph_to_db(project_id: str, graph_data: Dict[str, Any]):
    """Save graph nodes and edges to database"""
    with get_db_connection() as conn:
        # First, create nodes
        for node in graph_data['nodes']:
            node_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO node (id, project_id, original_id, label, summary)
                VALUES (?, ?, ?, ?, ?)
            """, (node_id, project_id, node['id'], node['label'], node['summary']))
            
            # Save learning objectives
            for obj in node.get('learning_objectives', []):
                conn.execute("""
                    INSERT INTO learning_objective (id, node_id, description)
                    VALUES (?, ?, ?)
                """, (str(uuid.uuid4()), node_id, obj['description']))
        
        # Then create edges
        for edge in graph_data['edges']:
            conn.execute("""
                INSERT INTO edge (source, target, project_id, confidence, rationale)
                VALUES (?, ?, ?, ?, ?)
            """, (edge['source'], edge['target'], project_id, 
                 edge.get('confidence'), edge.get('rationale')))
        
        conn.commit()


def create_session(project_id: str, node_id: str) -> str:
    """Create a new learning session and return its ID"""
    session_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        # Get the session number for this project
        cursor = conn.execute("""
            SELECT COUNT(*) + 1 FROM session WHERE project_id = ?
        """, (project_id,))
        session_number = cursor.fetchone()[0]
        
        # Create the session
        conn.execute("""
            INSERT INTO session (id, project_id, node_id, session_number)
            VALUES (?, ?, ?, ?)
        """, (session_id, project_id, node_id, session_number))
        
        conn.commit()
    
    return session_id


def complete_session(session_id: str, final_score: float):
    """Mark a session as completed with final score"""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE session 
            SET status = 'completed', 
                final_score = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (final_score, session_id))
        conn.commit()


def get_next_nodes(project_id: str) -> List[Dict[str, Any]]:
    """
    Get up to 2 lowest-mastery unlocked nodes.
    A node is unlocked if all its prerequisites have mastery >= MASTERY_THRESHOLD
    """
    query = """
    WITH prerequisite_check AS (
        SELECT n.id, n.label, n.mastery,
               COUNT(e.source) as prereq_count,
               SUM(CASE WHEN pn.mastery >= ? THEN 1 ELSE 0 END) as met_count
        FROM node n
        LEFT JOIN edge e ON e.target = n.original_id AND e.project_id = n.project_id
        LEFT JOIN node pn ON pn.original_id = e.source AND pn.project_id = n.project_id
        WHERE n.project_id = ?
        GROUP BY n.id
    )
    SELECT id, label FROM prerequisite_check
    WHERE prereq_count = 0 OR prereq_count = met_count
    ORDER BY mastery ASC
    LIMIT 2
    """
    
    with get_db_connection() as conn:
        cursor = conn.execute(query, (MASTERY_THRESHOLD, project_id))
        return [dict(row) for row in cursor.fetchall()]


def update_mastery(node_id: str, lo_scores: Dict[str, float]):
    """Update learning objective and node mastery scores"""
    with get_db_connection() as conn:
        # Update each LO mastery with simple averaging
        for lo_id, score in lo_scores.items():
            # Get current mastery
            cursor = conn.execute(
                "SELECT mastery FROM learning_objective WHERE id = ?", 
                (lo_id,)
            )
            row = cursor.fetchone()
            if row:
                old_mastery = row[0]
                new_mastery = (old_mastery + score) / 2
                
                conn.execute(
                    "UPDATE learning_objective SET mastery = ? WHERE id = ?",
                    (new_mastery, lo_id)
                )
        
        # Calculate node mastery as average of all LOs
        cursor = conn.execute("""
            SELECT AVG(mastery) FROM learning_objective WHERE node_id = ?
        """, (node_id,))
        avg_mastery = cursor.fetchone()[0] or 0.0
        
        # Update node mastery
        conn.execute(
            "UPDATE node SET mastery = ? WHERE id = ?",
            (avg_mastery, node_id)
        )
        
        conn.commit()


def save_transcript(session_id: str, turn_idx: int, role: str, content: str):
    """Save a transcript entry to the database"""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO transcript (session_id, turn_idx, role, content)
            VALUES (?, ?, ?, ?)
        """, (session_id, turn_idx, role, content))
        conn.commit()


def get_project(project_id: str) -> Optional[Dict]:
    """Get project details by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM project WHERE id = ?", 
            (project_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None


def get_node_with_objectives(node_id: str) -> Optional[Dict]:
    """Get node details with its learning objectives"""
    with get_db_connection() as conn:
        # Get node
        cursor = conn.execute(
            "SELECT * FROM node WHERE id = ?",
            (node_id,)
        )
        node = cursor.fetchone()
        if not node:
            return None
        
        node_dict = dict(node)
        
        # Get learning objectives
        cursor = conn.execute(
            "SELECT id, description, mastery FROM learning_objective WHERE node_id = ?",
            (node_id,)
        )
        node_dict['learning_objectives'] = [dict(row) for row in cursor.fetchall()]
        
        return node_dict


def get_transcript_for_session(session_id: str) -> List[Dict[str, Any]]:
    """Get all transcript entries for a session"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT turn_idx, role, content 
            FROM transcript 
            WHERE session_id = ? 
            ORDER BY turn_idx
        """, (session_id,))
        
        return [
            {"turn_idx": row[0], "role": row[1], "content": row[2]}
            for row in cursor.fetchall()
        ]


def get_latest_session_for_node(project_id: str, node_id: str) -> Optional[str]:
    """Get the most recent incomplete session for a node in a project"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id 
            FROM session 
            WHERE project_id = ? 
              AND node_id = ?
              AND status = 'in_progress'
            ORDER BY started_at DESC 
            LIMIT 1
        """, (project_id, node_id))
        
        result = cursor.fetchone()
        return result[0] if result else None


def get_all_projects() -> List[Dict[str, Any]]:
    """Get all projects with basic stats"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                p.id,
                p.topic,
                p.created_at,
                COUNT(DISTINCT n.id) as total_nodes,
                COUNT(DISTINCT CASE WHEN n.mastery >= 0.7 THEN n.id END) as mastered_nodes,
                ROUND(AVG(n.mastery) * 100) as progress
            FROM project p
            LEFT JOIN node n ON p.id = n.project_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        
        return [
            {
                "id": row[0],
                "topic": row[1],
                "created_at": row[2],
                "total_nodes": row[3],
                "mastered_nodes": row[4],
                "progress": int(row[5] or 0)
            }
            for row in cursor.fetchall()
        ]


def has_previous_sessions(project_id: str, exclude_session_id: Optional[str] = None) -> bool:
    """Check if a project has any completed sessions (excluding the given session)"""
    with get_db_connection() as conn:
        query = """
            SELECT COUNT(*) 
            FROM session 
            WHERE project_id = ? 
              AND status = 'completed'
        """
        params = [project_id]
        
        if exclude_session_id:
            query += " AND id != ?"
            params.append(exclude_session_id)
        
        cursor = conn.execute(query, params)
        count = cursor.fetchone()[0]
        return count > 0


def get_session_stats(project_id: str) -> Dict[str, Any]:
    """Get session statistics for a project"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                AVG(CASE WHEN status = 'completed' THEN final_score END) as avg_score
            FROM session
            WHERE project_id = ?
        """, (project_id,))
        
        row = cursor.fetchone()
        return {
            "total_sessions": row[0],
            "completed_sessions": row[1],
            "average_score": round(row[2], 2) if row[2] else 0
        }


def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """Get full session information including project and node details"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                s.id,
                s.project_id,
                s.node_id,
                s.status,
                s.session_number,
                s.final_score,
                p.topic as project_topic,
                n.label as node_label,
                n.original_id as node_original_id
            FROM session s
            JOIN project p ON s.project_id = p.id
            JOIN node n ON s.node_id = n.id
            WHERE s.id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "project_id": row[1],
                "node_id": row[2],
                "status": row[3],
                "session_number": row[4],
                "final_score": row[5],
                "project_topic": row[6],
                "node_label": row[7],
                "node_original_id": row[8]
            }
        return None


# Initialize database on module import
if __name__ != "__main__":
    init_database() 