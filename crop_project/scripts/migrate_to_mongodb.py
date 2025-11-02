import sqlite3
from datetime import datetime, timezone
import os
import sys
from bson import ObjectId

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.mongodb import (
    client, crops_collection, soil_types_collection,
    growth_stages_collection, readings_collection, logs_collection, init_mongodb, clear_collections
)

def _has_required_tables(db_path: str) -> bool:
    """Return True if the SQLite DB has the required tables."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('crops','soil_types','growth_stages','readings')")
        names = {row[0] for row in cur.fetchall()}
        return {'crops', 'soil_types', 'growth_stages', 'readings'}.issubset(names)
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _resolve_sqlite_path(default_path: str) -> str:
    """Try multiple candidates and return the first DB that has required tables."""
    # Candidates relative to project root (this file is scripts/..)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        default_path,
        os.path.join(project_root, 'sql', 'crop_monitoring.db'),
        os.path.join(project_root, 'crop_monitoring.db'),
    ]
    for p in candidates:
        if os.path.exists(p) and _has_required_tables(p):
            return p
    # If none matched, return the default (will error later with a clear message)
    return default_path


def migrate_sqlite_to_mongodb(sqlite_db_path):
    """Migrate data from SQLite to MongoDB"""
    # Initialize MongoDB
    init_mongodb()
    
    # Clear existing data (optional, comment out if you want to keep existing data)
    clear_collections()
    
    # Resolve and validate SQLite DB path
    sqlite_db_path = _resolve_sqlite_path(sqlite_db_path)
    if not os.path.exists(sqlite_db_path):
        raise FileNotFoundError(f"SQLite DB not found at: {sqlite_db_path}")
    if not _has_required_tables(sqlite_db_path):
        raise RuntimeError(f"SQLite DB at {sqlite_db_path} does not contain required tables (crops, soil_types, growth_stages, readings)")

    # Connect to SQLite
    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Create a mapping of old IDs to new ObjectIds
        crop_id_map = {}
        soil_type_id_map = {}
        growth_stage_id_map = {}
        
        # Migrate crops
        cursor.execute("SELECT * FROM crops")
        for row in cursor.fetchall():
            crop = dict(zip([col[0] for col in cursor.description], row))
            # Create a new document with _id
            result = crops_collection.insert_one({
                "name": crop["name"]
            })
            # Store the mapping from old ID to new ObjectId
            crop_id_map[crop["id"]] = str(result.inserted_id)
        print(f"Migrated {crops_collection.count_documents({})} crops")
        
        # Migrate soil types
        cursor.execute("SELECT * FROM soil_types")
        for row in cursor.fetchall():
            soil_type = dict(zip([col[0] for col in cursor.description], row))
            result = soil_types_collection.insert_one({
                "name": soil_type["name"]
            })
            soil_type_id_map[soil_type["id"]] = str(result.inserted_id)
        print(f"Migrated {soil_types_collection.count_documents({})} soil types")
        
        # Migrate growth stages
        cursor.execute("SELECT * FROM growth_stages")
        for row in cursor.fetchall():
            stage = dict(zip([col[0] for col in cursor.description], row))
            result = growth_stages_collection.insert_one({
                "name": stage["name"]
            })
            growth_stage_id_map[stage["id"]] = str(result.inserted_id)
        print(f"Migrated {growth_stages_collection.count_documents({})} growth stages")
        
        # Migrate readings
        cursor.execute("SELECT * FROM readings")
        for row in cursor.fetchall():
            reading = dict(zip([col[0] for col in cursor.description], row))
            
            # Convert timestamp to datetime if it's a string
            if "timestamp" in reading and reading["timestamp"] and isinstance(reading["timestamp"], str):
                reading["timestamp"] = datetime.fromisoformat(reading["timestamp"])
            elif "timestamp" not in reading:
                reading["timestamp"] = datetime.now(timezone.utc)
                
            # Map old IDs to new ObjectIds
            reading["crop_id"] = crop_id_map.get(reading.get("crop_id"))
            reading["growth_stage_id"] = growth_stage_id_map.get(reading.get("growth_stage_id"))

            # Preserve legacy numeric id for backward compatibility
            # Ensure it's an int if present
            if "id" in reading and reading["id"] is not None:
                try:
                    reading["id"] = int(reading["id"])
                except Exception:
                    pass

            # Insert the reading
            readings_collection.insert_one(reading)
        print(f"Migrated {readings_collection.count_documents({})} readings")
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        # Close connections
        conn.close()
        client.close()

if __name__ == "__main__":
    # Allow optional CLI path override
    cli_path = sys.argv[1] if len(sys.argv) > 1 else "crop_monitoring.db"
    migrate_sqlite_to_mongodb(cli_path)
