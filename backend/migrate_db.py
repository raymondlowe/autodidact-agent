"""
Database migration script to add session table and update schema
Run this to migrate existing databases to the new structure
"""

import sqlite3
from pathlib import Path

def migrate_database():
    """Migrate existing database to add session table"""
    db_path = Path.home() / ".autodidact" / "autodidact.db"
    
    if not db_path.exists():
        print("No existing database found. Nothing to migrate.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if session table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='session'
        """)
        
        if cursor.fetchone():
            print("Session table already exists. Migration not needed.")
            return
        
        print("Starting database migration...")
        
        # Create the new session table
        cursor.execute("""
            CREATE TABLE session (
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
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_session_project ON session(project_id)")
        cursor.execute("CREATE INDEX idx_session_node ON session(node_id)")
        
        # Add foreign key constraint to transcript table
        # Note: SQLite doesn't support ALTER TABLE ADD CONSTRAINT
        # So we need to recreate the table
        
        # First, rename the old transcript table
        cursor.execute("ALTER TABLE transcript RENAME TO transcript_old")
        
        # Create new transcript table with foreign key
        cursor.execute("""
            CREATE TABLE transcript (
                session_id TEXT NOT NULL,
                turn_idx INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, turn_idx),
                FOREIGN KEY (session_id) REFERENCES session(id)
            )
        """)
        
        # Create index
        cursor.execute("CREATE INDEX idx_transcript_session ON transcript(session_id)")
        
        # Migrate existing transcript data
        # We'll create dummy sessions for existing transcripts
        cursor.execute("SELECT DISTINCT session_id FROM transcript_old")
        old_sessions = cursor.fetchall()
        
        for (old_session_id,) in old_sessions:
            # Try to infer project and node from transcript content
            cursor.execute("""
                SELECT content FROM transcript_old 
                WHERE session_id = ? AND turn_idx = 0 AND role = 'assistant'
                LIMIT 1
            """, (old_session_id,))
            
            first_message = cursor.fetchone()
            if first_message:
                # Try to find a node that matches the content
                cursor.execute("""
                    SELECT n.id, n.project_id 
                    FROM node n
                    WHERE ? LIKE '%' || n.label || '%'
                    LIMIT 1
                """, (first_message[0],))
                
                node_match = cursor.fetchone()
                if node_match:
                    node_id, project_id = node_match
                    
                    # Create a session record
                    cursor.execute("""
                        INSERT INTO session (id, project_id, node_id, session_number, status)
                        VALUES (?, ?, ?, 1, 'completed')
                    """, (old_session_id, project_id, node_id))
                    
                    # Copy transcript entries
                    cursor.execute("""
                        INSERT INTO transcript 
                        SELECT * FROM transcript_old WHERE session_id = ?
                    """, (old_session_id,))
        
        # Drop the old transcript table
        cursor.execute("DROP TABLE transcript_old")
        
        conn.commit()
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database() 