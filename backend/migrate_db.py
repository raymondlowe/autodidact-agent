"""
Database migration script for Autodidact
Adds job_id, status, and name fields to project table
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


def migrate_add_name_field():
    """Add name field to project table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(project)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add name if it doesn't exist
        if 'name' not in columns:
            cursor.execute("ALTER TABLE project ADD COLUMN name TEXT")
            print("Added name column to project table")
            
            # Update existing projects to use first 50 chars of topic as name
            cursor.execute("SELECT id, topic FROM project")
            projects = cursor.fetchall()
            
            for project in projects:
                # Take first line of topic and limit to 50 chars
                topic = project['topic']
                name = topic.split('\n')[0][:50]
                if len(name) < len(topic.split('\n')[0]):
                    name += '...'
                
                cursor.execute("UPDATE project SET name = ? WHERE id = ?", (name, project['id']))
            
            print(f"Updated {len(projects)} existing projects with names")
        
        conn.commit()
        print("Name field migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrate_add_hours_field():
    """Add hours field to project table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(project)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add hours if it doesn't exist
        if 'hours' not in columns:
            cursor.execute("ALTER TABLE project ADD COLUMN hours INTEGER DEFAULT 5")
            print("Added hours column to project table")
            
            # Update existing projects to have default 5 hours
            cursor.execute("UPDATE project SET hours = 5 WHERE hours IS NULL")
            print("Updated existing projects to default 5 hours")
        
        conn.commit()
        print("Hours field migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_job_fields()
    migrate_add_name_field()
    migrate_add_hours_field() 