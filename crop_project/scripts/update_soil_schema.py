import sqlite3
from pathlib import Path

def update_schema():
    # Path to the database
    db_path = Path(__file__).parent.parent / 'crop_monitoring.db'
    
    # Connect to the database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION;")
        
        # 1. Add soil_name column if it doesn't exist
        cursor.execute("PRAGMA foreign_keys=off;")
        
        # 2. Create a new table with the updated schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_id INTEGER,
            soil_name TEXT,
            growth_stage_id INTEGER,
            moi INTEGER,
            temp FLOAT,
            humidity FLOAT,
            result INTEGER,
            timestamp TIMESTAMP,
            FOREIGN KEY (crop_id) REFERENCES crops (id),
            FOREIGN KEY (growth_stage_id) REFERENCES growth_stages (id)
        );
        """)
        
        # 3. Copy data from old table to new table with soil names
        cursor.execute("""
        INSERT INTO readings_new
        SELECT 
            r.id, 
            r.crop_id, 
            st.name as soil_name, 
            r.growth_stage_id, 
            r.moi, 
            r.temp, 
            r.humidity, 
            r.result, 
            r.timestamp
        FROM readings r
        LEFT JOIN soil_types st ON r.soil_type_id = st.id;
        """)
        
        # 4. Drop the old table
        cursor.execute("DROP TABLE readings;")
        
        # 5. Rename the new table
        cursor.execute("ALTER TABLE readings_new RENAME TO readings;")
        
        # 6. Recreate indexes if needed
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_crop_id ON readings(crop_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_soil_name ON readings(soil_name);")
        
        # 7. Commit the transaction
        cursor.execute("COMMIT;")
        cursor.execute("PRAGMA foreign_keys=on;")
        
        print("✅ Database schema updated successfully!")
        
    except Exception as e:
        # Rollback in case of error
        cursor.execute("ROLLBACK;")
        print(f"❌ Error updating schema: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database schema update...")
    update_schema()
    print("Done!")
