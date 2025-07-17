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
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.debug(f"get_db_connection called, DB_PATH={DB_PATH}")
    ensure_db_directory()
    logger.debug("Database directory ensured")
    
    try:
        logger.debug("Attempting to connect to SQLite database...")
        conn = sqlite3.connect(str(DB_PATH))
        logger.debug("SQLite connection established")
        conn.row_factory = sqlite3.Row  # Enable column access by name
        logger.debug("Row factory set")
        
        try:
            yield conn
            logger.debug("Connection yielded successfully")
        finally:
            logger.debug("Closing database connection...")
            conn.close()
            logger.debug("Database connection closed")
            
    except Exception as e:
        logger.error(f"Error in get_db_connection: {type(e).__name__}: {str(e)}")
        logger.exception("Full traceback:")
        raise


def init_database():
    """Initialize the database with the schema"""
    schema = """
    CREATE TABLE IF NOT EXISTS project (
        id TEXT PRIMARY KEY,
        name TEXT,
        topic TEXT NOT NULL,
        report_path TEXT,
        resources_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        job_id TEXT,
        model_used TEXT,
        status TEXT DEFAULT 'completed',
        hours INTEGER DEFAULT 5
    );

    CREATE TABLE IF NOT EXISTS node (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        original_id TEXT,
        label TEXT NOT NULL,
        summary TEXT,
        mastery REAL DEFAULT 0.0,
        references_sections_json TEXT,
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
        project_id TEXT NOT NULL,
        node_id TEXT NOT NULL,
        idx_in_node INTEGER NOT NULL,
        description TEXT NOT NULL,
        mastery REAL DEFAULT 0.0,
        FOREIGN KEY (project_id) REFERENCES project(id),
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
    CREATE INDEX IF NOT EXISTS idx_lo_project ON learning_objective(project_id);
    CREATE INDEX IF NOT EXISTS idx_session_project ON session(project_id);
    CREATE INDEX IF NOT EXISTS idx_session_node ON session(node_id);
    CREATE INDEX IF NOT EXISTS idx_transcript_session ON transcript(session_id);
    """
    
    with get_db_connection() as conn:
        conn.executescript(schema)
        conn.commit()


def create_project(topic: str, report_path: str, resources: Dict) -> str:
    """Create a new project and return its ID"""
    project_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                INSERT INTO project (id, topic, report_path, resources_json)
                VALUES (?, ?, ?, ?)
            """, (
                project_id,
                topic,
                report_path,
                json.dumps(resources)
            ))
            conn.commit()
            return project_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to create project: {str(e)}")


def create_project_with_job(topic: str, name: str, job_id: str, model_used: str, status: str = 'processing', hours: int = 5) -> str:
    """Create a new project with a job ID for background processing"""
    project_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                INSERT INTO project (id, name, topic, job_id, model_used, status, hours)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                name,
                topic,
                job_id,
                model_used,
                status,
                hours
            ))
            conn.commit()
            return project_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to create project with job: {str(e)}")


# add an update_project_with_job function
def update_project_with_job(project_id: str, job_id: str, model_used: str, status: str = 'processing'):
    """Update a project with a job ID for background processing"""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE project SET job_id = ?, model_used = ?, status = ? WHERE id = ?
        """, (job_id, model_used, status, project_id))
        conn.commit()

def update_project_status(project_id: str, status: str):
    """Update the status of a project"""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE project SET status = ? WHERE id = ?
        """, (status, project_id))
        conn.commit()


def update_project_completed_and_save_graph_to_db(project_id: str, report_path: str, 
                           resources: List[Dict], graph_data: Dict[str, Any], status: str = 'completed'):
    """Update a project when its deep research job completes
    Also save graph nodes, edges, and learning_objectives to their respective db tables
    """
    with get_db_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                UPDATE project 
                SET report_path = ?, 
                    resources_json = ?,
                    status = ?
                WHERE id = ?
            """, (
                report_path,
                json.dumps(resources),
                status,
                project_id
            ))

            # Create nodes
            for node in graph_data['nodes']:
                node_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO node (id, project_id, original_id, label, summary, references_sections_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (node_id, project_id, node['id'], node['title'], '', json.dumps(node.get('resource_pointers', []))))

                # Save learning objectives
                for idx, lo in enumerate(node.get('learning_objectives', [])):
                    print(f"[update_project_completed_and_save_graph_to_db] Saving learning objective: {lo}")
                    conn.execute("""
                        INSERT INTO learning_objective (id, project_id, node_id, idx_in_node, description)
                        VALUES (?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), project_id, node_id, idx, lo['description']))
            
            # Create edges
            for edge in graph_data['edges']:
                conn.execute("""
                    INSERT INTO edge (source, target, project_id, confidence, rationale)
                    VALUES (?, ?, ?, ?, ?)
                """, (edge['source'], edge['target'], project_id, 
                    edge.get('confidence', 1.0), edge.get('rationale', '')))
                
            # after all above have been done, commit the transaction
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to update project: {str(e)}")


def check_and_complete_job(project_id: str, job_id: str) -> bool:
    """
    Check job status and update project if complete.
    Returns True if job is complete (either success or failure), False if still processing.
    """
    from utils.providers import create_client
    from utils.config import save_project_files
    from utils.deep_research import deep_research_output_cleanup

    # Sanitize job_id to remove any whitespace or newline characters
    clean_job_id = job_id.strip() if job_id else ""
    
    print(f"[check_and_complete_job] Checking job {clean_job_id} for project {project_id}")
    
    try:

        # Create provider-aware client
        client = create_client()
        
        # Retrieve job status
        job = client.responses.retrieve(job_id)

        
        if job.status == "completed":
            print(f"[check_and_complete_job] Job {clean_job_id} completed successfully")

            json_str = job.output_text
            
            # TODO: remove this after confirming that job.output_text works in all cases
            # # Extract the result
            # content_block = job.output[-1].content[0]
            # if content_block.type != "output_text":
            #     raise RuntimeError("Unexpected content block type")
            
            # fixes small typos, invalid JSON, etc, by passing to 4o or o4-mini to fix
            json_str = deep_research_output_cleanup(json_str, client)
            
            # Parse the JSON response
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"[check_and_complete_job] Failed to parse JSON: {e}")
                update_project_status(project_id, 'failed')
                return True
            
            # Validate and extract components
            if "resources" in data and "nodes" in data:
                resources = data["resources"]
                graph = {
                    "nodes": data["nodes"],
                    "edges": []  # we will later build edges from prerequisite_node_ids
                }
                
                # Build edges from prerequisite_node_ids
                for node in data["nodes"]:
                    if "prerequisite_node_ids" in node and node["prerequisite_node_ids"]:
                        for prereq in node["prerequisite_node_ids"]:
                            graph["edges"].append({
                                "source": prereq,
                                "target": node["id"],
                                "confidence": 1.0
                            })
                
                # Create report from resources
                project = get_project(project_id)
                report_markdown = f"# {project['name']}\n\n## Resources\n\n"
                for resource in data["resources"]:
                    report_markdown += f"- [{resource['title']}]({resource['url']}) - {resource['scope']}\n"
                
            else:
                # missing data. should we just throw an error here?
                print("Invalid/empty data returned from deep research")
                update_project_status(project_id, 'failed')
                return True

            # Ensure nodes have properly structured learning_objectives 
            # (until this point, learning_objectives is a list of strings, now its a list of dicts with a "description" key)
            for node in graph["nodes"]:
                if "learning_objectives" in node:
                    node["learning_objectives"] = [{"description": obj} for obj in node["learning_objectives"]]
                elif "objectives" in node:
                    # old syntax
                    node["learning_objectives"] = [{"description": obj} for obj in node["objectives"]]
                else:
                    # Generate defaults. Not sure if this is even hit tbh
                    node["learning_objectives"] = [
                        {"description": f"Understand the key concepts of {node.get('label', node.get('title', 'this topic'))}"},
                        {"description": f"Apply principles in practice"},
                        {"description": f"Analyze relationships with related topics"},
                        {"description": f"Evaluate different approaches"},
                        {"description": f"Create solutions using this knowledge"}
                    ]
            
            # Save files
            report_path = save_project_files(
                project_id,
                report_markdown,
                graph,
                data
            )
            
            # Update project to mark it as completed.
            # also Save graph nodes, edges, and learning_objectives to their respective db tables
            update_project_completed_and_save_graph_to_db(
                project_id,
                report_path=report_path,
                resources=resources,
                graph_data=graph,
                status='completed'
            )
            
            print(f"[check_and_complete_job] Project {project_id} updated successfully")
            return True
            
        elif job.status == "failed":
            print(f"[check_and_complete_job] Job {clean_job_id} failed")
            update_project_status(project_id, 'failed')
            return True
            
        elif job.status == "cancelled":
            print(f"[check_and_complete_job] Job {clean_job_id} was cancelled")
            update_project_status(project_id, 'failed')
            return True
            
        else: # in_progress, queued, incomplete
            # Still processing
            print(f"[check_and_complete_job] Job {clean_job_id} still processing (status: {job.status})")
            return False
            
    except Exception as e:
        print(f"[check_and_complete_job] Error checking job: {e}")
        # Don't mark as failed on transient errors
        return False
    
def check_job(job_id: str) -> bool:
    """
    Check job status and returns result.
    """
    from utils.providers import create_client

    # Sanitize job_id to remove any whitespace or newline characters
    clean_job_id = job_id.strip() if job_id else ""
    
    print(f"[check_job] Checking job {clean_job_id}")
    
    try:

        # Create provider-aware client
        client = create_client()
        
        # Retrieve job status
        job = client.responses.retrieve(job_id)

        return job
    except Exception as e:
        print(f"[check_job] Error checking job: {e}")
        # Don't mark as failed on transient errors
        return None


def create_session(project_id: str, node_id: str) -> str:
    """Create a new learning session and return its ID"""
    logger.info(f"create_session called with project_id={project_id}, node_id={node_id}")
    session_id = str(uuid.uuid4())
    logger.debug(f"Generated session_id: {session_id}")
    
    try:
        logger.debug("Attempting to get database connection...")
        with get_db_connection() as conn:
            logger.debug("Got database connection successfully")
            
            # Get the session number for this project
            logger.debug(f"Querying session count for project {project_id}")
            cursor = conn.execute("""
                SELECT COUNT(*) + 1 FROM session WHERE project_id = ?
            """, (project_id,))
            session_number = cursor.fetchone()[0]
            logger.debug(f"Session number for this project: {session_number}")
            
            # Create the session
            logger.debug(f"Inserting new session: id={session_id}, project_id={project_id}, node_id={node_id}, session_number={session_number}")
            conn.execute("""
                INSERT INTO session (id, project_id, node_id, session_number)
                VALUES (?, ?, ?, ?)
            """, (session_id, project_id, node_id, session_number))
            
            logger.debug("Committing transaction...")
            conn.commit()
            logger.debug("Transaction committed successfully")
            
        logger.info(f"Session created successfully with id: {session_id}")
        return session_id
        
    except Exception as e:
        logger.error(f"Error in create_session: {type(e).__name__}: {str(e)}")
        logger.exception("Full traceback:")
        
        # Run debug diagnostics
        if "database is locked" in str(e).lower():
            logger.warning("Database lock detected, running diagnostics...")
            debug_database_connections()
        
        raise


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
    WHERE (prereq_count = 0 OR prereq_count = met_count)
    AND mastery < ?
    ORDER BY mastery ASC
    LIMIT 2
    """
    
    with get_db_connection() as conn:
        cursor = conn.execute(query, (MASTERY_THRESHOLD, project_id, MASTERY_THRESHOLD))
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

def get_edges_for_project(conn, project_id: str) -> List[Dict[str, Any]]:
    """Get all edges for a project"""
    cursor = conn.execute("SELECT * FROM edge WHERE project_id = ?", (project_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_nodes_for_project(conn, project_id: str) -> List[Dict[str, Any]]:
    """Get all nodes for a project"""
    cursor = conn.execute("SELECT * FROM node WHERE project_id = ?", (project_id,))
    nodes = [dict(row) for row in cursor.fetchall()]

    cursor2 = conn.execute("SELECT * FROM learning_objective WHERE project_id = ?", (project_id,))
    raw_learning_objectives = [dict(row) for row in cursor2.fetchall()]

    # for every node, add the learning objectives to the node
    for node in nodes:
        # sort below by `idx_in_node`
        node['learning_objectives'] = sorted(
            [lo for lo in raw_learning_objectives if lo['node_id'] == node['id']],
            key=lambda x: x['idx_in_node']
        )

    # for every node, unfurl the `references_sections_json` into a list of sections
    for node in nodes:
        node['references_sections'] = json.loads(node['references_sections_json'])
    return nodes


def get_project(project_id: str) -> Optional[Dict]:
    """Get project details by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, topic, report_path, resources_json, created_at, job_id, model_used, status, hours FROM project WHERE id = ?", 
            (project_id,)
        )
        row = cursor.fetchone()
        if row:
            project_id = row[0]
            project_data = {
                "id": project_id,
                "name": row[1],
                "topic": row[2],
                "report_path": row[3],
                "resources_json": row[4],
                "created_at": row[5],
                "job_id": row[6],
                "model_used": row[7],
                "status": row[8] or 'completed',  # Default for old projects
                "hours": row[9] or 5  # Default to 5 hours for old projects
            }
            # first get all the edges which have `project_id` = project_id
            edges = get_edges_for_project(conn, project_id)
            nodes = get_nodes_for_project(conn, project_id)

            graph = {
                "nodes": nodes,
                "edges": edges
            }

            project_data['graph'] = graph

            resources_json_str = project_data['resources_json']
            project_data['resources'] = json.loads(resources_json_str) if resources_json_str else []
            project_data['resources_json'] = None

            # print(f"[get_project] Project {project_id} graph: {graph}")
            return project_data
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

        # Fetch project's `topic` and `resources_json`
        cursor = conn.execute(
            "SELECT topic, resources_json FROM project WHERE id = ?",
            (node_dict['project_id'],)
        )
        project = cursor.fetchone()
        node_dict['project_topic'] = project[0]

        node_references_sections = json.loads(node_dict.get('references_sections_json', '[]'))
        project_resources = json.loads(project[1]) if project[1] else []

        # for each node_references_sections, add the `references` to the section
        for section in node_references_sections:
            # find the reference with same `rid` in project_resources
            project_ref = [ref for ref in project_resources if ref['rid'] == section['rid']]
            project_ref = project_ref[0] if project_ref else None 
            # copy everything from project_ref into the section
            section.update(project_ref)

        node_dict['references_sections_json'] = None
        node_dict['references_sections_resolved'] = node_references_sections
        
        # Get learning objectives
        cursor = conn.execute(
            "SELECT id, project_id, description, mastery, idx_in_node FROM learning_objective WHERE node_id = ? ORDER BY idx_in_node",
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
                p.name,
                p.topic,
                p.created_at,
                p.status,
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
                "name": row[1],
                "topic": row[2],
                "created_at": row[3],
                "status": row[4] or 'completed',  # Default to completed for old projects
                "total_nodes": row[5],
                "mastered_nodes": row[6],
                "progress": int(row[7] or 0)
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


def delete_project(project_id: str) -> bool:
    """
    Delete a project and all associated data.
    Returns True if successful, False otherwise.
    """
    import shutil
    from utils.providers import create_client
    
    try:
        # Step 1: Cancel active job if processing
        project = get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
            
        if project['status'] == 'processing' and project['job_id']:
            # Cancel the OpenAI job
            api_key = load_api_key()
            try:
                client = create_client()
                clean_job_id = project['job_id'].strip() if project['job_id'] else ""
                # FIXME: also cancel the job when we retry with o3?
                client.responses.cancel(clean_job_id)
                print(f"Cancelled job {clean_job_id} for project {project_id}")
            except Exception as e:
                print(f"Failed to cancel job {project['job_id']}: {e}")
                # Continue with deletion anyway
       
        # Step 2: Database deletion in transaction
        with get_db_connection() as conn:
            conn.execute("BEGIN TRANSACTION")
            
            try:
                # 1. Get all sessions for this project
                cursor = conn.execute(
                    "SELECT id FROM session WHERE project_id = ?", 
                    (project_id,)
                )
                session_ids = [row[0] for row in cursor.fetchall()]
                
                # 2. Delete transcripts for all sessions
                if session_ids:
                    placeholders = ','.join(['?' for _ in session_ids])
                    conn.execute(
                        f"DELETE FROM transcript WHERE session_id IN ({placeholders})",
                        session_ids
                    )
                    print(f"Deleted transcripts for {len(session_ids)} sessions")
                
                # 3. Delete all sessions
                cursor = conn.execute(
                    "DELETE FROM session WHERE project_id = ?",
                    (project_id,)
                )
                print(f"Deleted {cursor.rowcount} sessions")
                
                # 4. Delete learning objectives
                cursor = conn.execute(
                    "DELETE FROM learning_objective WHERE project_id = ?",
                    (project_id,)
                )
                print(f"Deleted {cursor.rowcount} learning objectives")
                
                # 5. Delete edges
                cursor = conn.execute(
                    "DELETE FROM edge WHERE project_id = ?",
                    (project_id,)
                )
                print(f"Deleted {cursor.rowcount} edges")
                
                # 6. Delete nodes
                cursor = conn.execute(
                    "DELETE FROM node WHERE project_id = ?",
                    (project_id,)
                )
                print(f"Deleted {cursor.rowcount} nodes")
                
                # 7. Delete project record
                cursor = conn.execute(
                    "DELETE FROM project WHERE id = ?",
                    (project_id,)
                )
                print(f"Deleted project record")
                
                conn.commit()
                print(f"Successfully deleted all database records for project {project_id}")
                
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to delete project from database: {str(e)}")
        
        # Step 3: Delete project files
        project_dir = Path.home() / '.autodidact' / 'projects' / project_id
        
        if project_dir.exists():
            try:
                shutil.rmtree(project_dir)
                print(f"Deleted project files at {project_dir}")
            except Exception as e:
                print(f"Warning: Failed to delete project files: {e}")
                # Don't fail the whole operation if file deletion fails
        
        return True
        
    except Exception as e:
        print(f"Error in delete_project: {str(e)}")
        return False


def debug_database_connections():
    """Debug function to check for database connections and locks"""
    logger.info("=== DATABASE DEBUG INFO ===")
    logger.info(f"Database path: {DB_PATH}")
    logger.info(f"Database exists: {DB_PATH.exists()}")
    
    if DB_PATH.exists():
        logger.info(f"Database size: {DB_PATH.stat().st_size} bytes")
        logger.info(f"Database permissions: {oct(DB_PATH.stat().st_mode)}")
        
        # Try to check for processes with the database file open
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for file in proc.open_files():
                        if str(DB_PATH) in file.path:
                            logger.warning(f"Process {proc.info['pid']} ({proc.info['name']}) has database file open")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            logger.debug("psutil not available for process checking")
    
    # Try a test connection
    try:
        test_conn = sqlite3.connect(str(DB_PATH), timeout=1.0)
        logger.info("Test connection successful")
        
        # Check journal mode
        cursor = test_conn.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        logger.info(f"Journal mode: {journal_mode}")
        
        # Check if there are any locks
        cursor = test_conn.execute("PRAGMA database_list")
        databases = cursor.fetchall()
        for db in databases:
            logger.info(f"Database: {db}")
        
        test_conn.close()
        logger.info("Test connection closed successfully")
        
    except Exception as e:
        logger.error(f"Test connection failed: {type(e).__name__}: {str(e)}")
    
    logger.info("=== END DATABASE DEBUG INFO ===")


# Initialize database on module import
if __name__ != "__main__":
    init_database() 