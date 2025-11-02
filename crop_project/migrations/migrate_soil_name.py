import sqlite3
from pathlib import Path

def migrate_database():
    """Migrate the database to use soil_name instead of soil_type_id"""
    # Updated path to look for the database in the parent directory
    db_path = Path(__file__).parent.parent / "crop_monitoring.db"
    backup_path = db_path.with_name("crop_monitoring_backup.db")
    
    print(f"Migrating database: {db_path}")
    print("Creating backup...")
    
    # Create a backup of the database
    with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
        dst.write(src.read())
    print(f"Backup created at: {backup_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION;")
        
        # Step 1: Add the new soil_name column
        print("Adding soil_name column to readings table...")
        cursor.execute("""
        ALTER TABLE readings 
        ADD COLUMN soil_name TEXT;
        """)
        
        # Step 2: Update existing records with soil names
        print("Updating existing records with soil names...")
        cursor.execute("""
        UPDATE readings 
        SET soil_name = (
            SELECT st.name 
            FROM soil_types st 
            WHERE st.id = readings.soil_type_id
        )
        WHERE soil_name IS NULL;
        """)
        
        # Step 3: Make soil_name required
        print("Making soil_name required...")
        
        # Execute each statement separately
        statements = [
            """
            CREATE TABLE readings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                soil_name TEXT NOT NULL,
                growth_stage_id INTEGER NOT NULL,
                moi INTEGER NOT NULL,
                temp REAL NOT NULL,
                humidity REAL NOT NULL,
                result INTEGER NOT NULL,
                timestamp TIMESTAMP,
                FOREIGN KEY (crop_id) REFERENCES crops (id),
                FOREIGN KEY (growth_stage_id) REFERENCES growth_stages (id)
            )
            """,
            """
            INSERT INTO readings_new (
                id, crop_id, soil_name, growth_stage_id, 
                moi, temp, humidity, result, timestamp
            )
            SELECT 
                id, crop_id, soil_name, growth_stage_id, 
                moi, temp, humidity, result, timestamp
            FROM readings
            """,
            "DROP TABLE readings",
            "ALTER TABLE readings_new RENAME TO readings",
            "CREATE INDEX ix_readings_crop_id ON readings (crop_id)",
            "CREATE INDEX ix_readings_soil_name ON readings (soil_name)",
            "CREATE INDEX ix_readings_growth_stage_id ON readings (growth_stage_id)",
            "CREATE INDEX ix_readings_timestamp ON readings (timestamp)"
        ]
        
        for statement in statements:
            cursor.execute(statement.strip())
            conn.commit()
        
        # Commit the transaction
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        print("Migration failed. The database has been restored to its original state.")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== Database Migration: Replace soil_type_id with soil_name ===")
    print("This script will modify your database. Make sure to back it up first!")
    confirm = input("Do you want to continue? (yes/no): ")
    
    if confirm.lower() == 'yes':
        migrate_database()
    else:
        print("Migration cancelled.")
