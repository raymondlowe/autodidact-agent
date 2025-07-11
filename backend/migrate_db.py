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


def migrate_rename_footnotes_to_resources():
    """Rename footnotes_json column to resources_json in project table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if old column exists and new column doesn't exist
        cursor.execute("PRAGMA table_info(project)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'footnotes_json' in columns and 'resources_json' not in columns:
            # SQLite doesn't support direct column rename, so we need to:
            # 1. Create new column
            # 2. Copy data
            # 3. Drop old column (which requires recreating the table)
            
            # Since SQLite doesn't support DROP COLUMN easily, we'll use a different approach:
            # Create the new column and copy data
            cursor.execute("ALTER TABLE project ADD COLUMN resources_json TEXT")
            cursor.execute("UPDATE project SET resources_json = footnotes_json")
            print("Renamed footnotes_json to resources_json in project table")
            
            # Note: The old column will remain but be unused. A full table recreation
            # would be needed to remove it, which is complex and risky for existing data.
            print("Note: The old footnotes_json column remains for backward compatibility")
        elif 'resources_json' in columns:
            print("resources_json column already exists")
        else:
            print("footnotes_json column not found - no migration needed")
        
        conn.commit()
        print("Footnotes to resources migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrate_add_references_sections_json():
    """Add references_sections_json column to node table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(node)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add references_sections_json if it doesn't exist
        if 'references_sections_json' not in columns:
            cursor.execute("ALTER TABLE node ADD COLUMN references_sections_json TEXT DEFAULT '[]'")
            print("Added references_sections_json column to node table")
            
            # Update existing nodes to have empty array
            cursor.execute("UPDATE node SET references_sections_json = '[]' WHERE references_sections_json IS NULL")
            print("Updated existing nodes to have empty sections array")
        else:
            print("references_sections_json column already exists")
        
        conn.commit()
        print("References sections migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrate_add_idx_in_node():
    """Add idx_in_node column to learning_objective table"""
    
    if not DB_PATH.exists():
        print("Database does not exist. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(learning_objective)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add idx_in_node if it doesn't exist
        if 'idx_in_node' not in columns:
            cursor.execute("ALTER TABLE learning_objective ADD COLUMN idx_in_node INTEGER DEFAULT 0")
            print("Added idx_in_node column to learning_objective table")
            
            # Update existing learning objectives with sequential indices
            cursor.execute("""
                SELECT DISTINCT node_id FROM learning_objective ORDER BY node_id
            """)
            node_ids = [row[0] for row in cursor.fetchall()]
            
            for node_id in node_ids:
                cursor.execute("""
                    SELECT id FROM learning_objective 
                    WHERE node_id = ? 
                    ORDER BY id
                """, (node_id,))
                lo_ids = [row[0] for row in cursor.fetchall()]
                
                for idx, lo_id in enumerate(lo_ids):
                    cursor.execute("""
                        UPDATE learning_objective 
                        SET idx_in_node = ? 
                        WHERE id = ?
                    """, (idx, lo_id))
            
            print(f"Updated {len(node_ids)} nodes with sequential indices")
        else:
            print("idx_in_node column already exists")
        
        conn.commit()
        print("Learning objective index migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_job_fields()
    migrate_add_name_field()
    migrate_add_hours_field()
    migrate_rename_footnotes_to_resources()
    migrate_add_references_sections_json()
    migrate_add_idx_in_node() 