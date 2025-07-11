"""
Database migration script for Autodidact
Adds job_id and status fields to project table
"""

import sqlite3
from pathlib import Path

# Use the same DB path as in db.py
DB_PATH = Path.home() / '.autodidact' / 'autodidact.db'

def migrate_add_job_fields():
    """Add job_id and status fields to project table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(project)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add job_id if it doesn't exist
        if 'job_id' not in columns:
            cursor.execute("ALTER TABLE project ADD COLUMN job_id TEXT")
            print("Added job_id column to project table")
        
        # Add status if it doesn't exist
        if 'status' not in columns:
            cursor.execute("ALTER TABLE project ADD COLUMN status TEXT DEFAULT 'completed'")
            print("Added status column to project table")
            
            # Update existing projects to have 'completed' status
            cursor.execute("UPDATE project SET status = 'completed' WHERE status IS NULL")
            print("Updated existing projects to 'completed' status")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_job_fields() 