"""
Database module for Autodidact
Handles SQLite database operations with direct SQL (no ORM)
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple
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

    CREATE TABLE IF NOT EXISTS transcript (
        session_id TEXT NOT NULL,
        turn_idx INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (session_id, turn_idx)
    );
    
    -- Create indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_node_project ON node(project_id);
    CREATE INDEX IF NOT EXISTS idx_node_original ON node(original_id);
    CREATE INDEX IF NOT EXISTS idx_edge_project ON edge(project_id);
    CREATE INDEX IF NOT EXISTS idx_lo_node ON learning_objective(node_id);
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


def save_graph_to_db(project_id: str, graph_data: Dict):
    """Save graph nodes and edges to database with transaction support"""
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            
            # Save nodes
            for node in graph_data['nodes']:
                node_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO node (id, project_id, original_id, label, summary)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    node_id,
                    project_id,
                    node['id'],
                    node['label'],
                    node['summary']
                ))
                
                # Save learning objectives
                for lo_desc in node.get('learning_objectives', []):
                    lo_id = str(uuid.uuid4())
                    conn.execute("""
                        INSERT INTO learning_objective (id, node_id, description)
                        VALUES (?, ?, ?)
                    """, (lo_id, node_id, lo_desc))
            
            # Save edges
            for edge in graph_data['edges']:
                conn.execute("""
                    INSERT INTO edge (source, target, project_id, confidence, rationale)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    edge['source'],
                    edge['target'],
                    project_id,
                    edge.get('confidence', 1.0),
                    edge.get('rationale', '')
                ))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to save graph to database: {str(e)}")


def get_next_nodes(project_id: str) -> List[Dict]:
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
    """Update learning objective and node mastery scores with error handling"""
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            
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
                SELECT AVG(mastery) as avg_mastery
                FROM learning_objective
                WHERE node_id = ?
            """, (node_id,))
            
            avg_mastery = cursor.fetchone()[0] or 0.0
            
            conn.execute(
                "UPDATE node SET mastery = ? WHERE id = ?",
                (avg_mastery, node_id)
            )
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to update mastery scores: {str(e)}")


def save_transcript(session_id: str, turn_idx: int, role: str, content: str):
    """Save a conversation turn to the transcript with error handling"""
    with get_db_connection() as conn:
        try:
            conn.execute("""
                INSERT INTO transcript (session_id, turn_idx, role, content)
                VALUES (?, ?, ?, ?)
            """, (session_id, turn_idx, role, content))
            conn.commit()
        except Exception as e:
            # Log but don't fail the session
            print(f"Warning: Failed to save transcript: {str(e)}")


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


def get_transcript_for_session(session_id: str) -> List[Dict]:
    """Get all transcript entries for a session (for recovery)"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT turn_idx, role, content 
            FROM transcript 
            WHERE session_id = ?
            ORDER BY turn_idx
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_latest_session_for_node(node_id: str) -> Optional[str]:
    """Get the most recent session ID for a node (for recovery)"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT t.session_id 
            FROM transcript t
            WHERE t.session_id IN (
                SELECT session_id FROM transcript 
                WHERE content LIKE '%' || (SELECT label FROM node WHERE id = ?) || '%'
            )
            ORDER BY t.created_at DESC
            LIMIT 1
        """, (node_id,))
        row = cursor.fetchone()
        return row[0] if row else None


def get_all_projects() -> List[Dict]:
    """Get all projects ordered by creation date"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, topic, created_at,
                   (SELECT COUNT(*) FROM node WHERE project_id = p.id AND mastery >= ?) as mastered_nodes,
                   (SELECT COUNT(*) FROM node WHERE project_id = p.id) as total_nodes
            FROM project p
            ORDER BY created_at DESC
        """, (MASTERY_THRESHOLD,))
        
        projects = []
        for row in cursor.fetchall():
            project = dict(row)
            # Calculate progress percentage
            if project['total_nodes'] > 0:
                project['progress'] = int((project['mastered_nodes'] / project['total_nodes']) * 100)
            else:
                project['progress'] = 0
            projects.append(project)
        
        return projects


# Initialize database on module import
if __name__ != "__main__":
    init_database() 