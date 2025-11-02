import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from .base import Database

class SQLiteDatabase(Database):
    def __init__(self, db_path: str = "sql/crop_monitoring.db"):
        # Create the sql directory if it doesn't exist
        db_dir = Path(__file__).parent.parent.parent / "sql"
        db_dir.mkdir(exist_ok=True)
        
        self.db_path = str(db_dir / Path(db_path).name)
        self.conn = None
        
    def connect(self):
        """Establish a connection to the SQLite database"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def get_crops(self) -> List[Dict[str, Any]]:
        """Retrieve all crops from the database"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM crops")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_soil_types(self) -> List[Dict[str, Any]]:
        """Retrieve all soil types from the database"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM soil_types")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_growth_stages(self) -> List[Dict[str, Any]]:
        """Retrieve all growth stages from the database"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM growth_stages")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_readings(self, skip: int = 0, limit: int = 100, reading_id: int = None, crop_id: int = None) -> List[Dict[str, Any]]:
        """Retrieve sensor readings with related data
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            reading_id: Optional reading ID to get a specific reading
            crop_id: Optional crop ID to filter by crop
            
        Returns:
            List of dictionaries containing reading data
        """
        with self.connect() as conn:
            cursor = conn.cursor()
            query = """
            SELECT 
                r.id, r.moi, r.temp, r.humidity, r.result, r.timestamp, r.soil_name,
                c.id as crop_id, c.name as crop_name,
                gs.id as growth_stage_id, gs.name as growth_stage_name
            FROM readings r
            JOIN crops c ON r.crop_id = c.id
            JOIN growth_stages gs ON r.growth_stage_id = gs.id
            """
            
            params = []
            conditions = []
            
            if reading_id is not None:
                conditions.append("r.id = ?")
                params.append(reading_id)
                
            if crop_id is not None:
                conditions.append("r.crop_id = ?")
                params.append(crop_id)
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY r.timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, skip])
            
            cursor.execute(query, params)
            
            # Convert to list of dictionaries and format the response
            readings = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                readings.append({
                    "id": row_dict["id"],
                    "crop_id": row_dict["crop_id"],
                    "crop_name": row_dict["crop_name"],
                    "soil_name": row_dict["soil_name"],
                    "growth_stage_id": row_dict["growth_stage_id"],
                    "growth_stage_name": row_dict["growth_stage_name"],
                    "moi": row_dict["moi"],
                    "temp": row_dict["temp"],
                    "humidity": row_dict["humidity"],
                    "result": row_dict["result"],
                    "timestamp": row_dict["timestamp"]
                })
            return readings
    
    def add_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new sensor reading to the database"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Get or create crop
            cursor.execute("SELECT id FROM crops WHERE name = ?", (reading_data['crop_name'],))
            crop = cursor.fetchone()
            if not crop:
                cursor.execute("INSERT INTO crops (name) VALUES (?)", (reading_data['crop_name'],))
                crop_id = cursor.lastrowid
            else:
                crop_id = crop['id']
            
            # Get or create growth stage
            cursor.execute("SELECT id FROM growth_stages WHERE name = ?", (reading_data['growth_stage_name'],))
            growth_stage = cursor.fetchone()
            if not growth_stage:
                cursor.execute("INSERT INTO growth_stages (name) VALUES (?)", (reading_data['growth_stage_name'],))
                growth_stage_id = cursor.lastrowid
            else:
                growth_stage_id = growth_stage['id']
            
            # Always include result in the columns with NULL if not provided
            columns = ['crop_id', 'soil_name', 'growth_stage_id', 'moi', 'temp', 'humidity', 'result', 'timestamp']
            values = [
                crop_id, 
                reading_data['soil_name'], 
                growth_stage_id, 
                reading_data['moi'], 
                reading_data['temp'], 
                reading_data['humidity'],
                reading_data.get('result'),  # This will be None if 'result' is not in reading_data
                datetime.utcnow().isoformat()  # Always use current time for new readings
            ]

            placeholders = ', '.join(['?'] * len(columns))
            sql = f"INSERT INTO readings ({', '.join(columns)}) VALUES ({placeholders})"

            cursor.execute(sql, tuple(values))
            conn.commit()
            reading_id = cursor.lastrowid
            
            # Return the complete reading with names
            cursor.execute("""
                SELECT r.*, 
                       c.name as crop_name,
                       g.name as growth_stage_name
                FROM readings r
                LEFT JOIN crops c ON r.crop_id = c.id
                LEFT JOIN growth_stages g ON r.growth_stage_id = g.id
                WHERE r.id = ?
            """, (reading_id,))
            return dict(cursor.fetchone())

    def update_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing sensor reading by id. Can also update crop_name and growth_stage_name."""
        if 'id' not in reading_data:
            raise ValueError("Reading identifier 'id' is required")

        reading_id = reading_data['id']
        with self.connect() as conn:
            cursor = conn.cursor()

            # Fetch existing reading
            cursor.execute("SELECT * FROM readings WHERE id = ?", (reading_id,))
            existing = cursor.fetchone()
            if not existing:
                raise ValueError("Reading not found")
            existing = dict(existing)

            # Resolve crop
            crop_id = existing['crop_id']
            if 'crop_name' in reading_data and reading_data['crop_name']:
                cursor.execute("SELECT id FROM crops WHERE name = ?", (reading_data['crop_name'],))
                crop = cursor.fetchone()
                if not crop:
                    cursor.execute("INSERT INTO crops (name) VALUES (?)", (reading_data['crop_name'],))
                    crop_id = cursor.lastrowid
                else:
                    crop_id = crop['id']

            # Resolve growth stage
            growth_stage_id = existing['growth_stage_id']
            if 'growth_stage_name' in reading_data and reading_data['growth_stage_name']:
                cursor.execute("SELECT id FROM growth_stages WHERE name = ?", (reading_data['growth_stage_name'],))
                gs = cursor.fetchone()
                if not gs:
                    cursor.execute("INSERT INTO growth_stages (name) VALUES (?)", (reading_data['growth_stage_name'],))
                    growth_stage_id = cursor.lastrowid
                else:
                    growth_stage_id = gs['id']

            # Prepare updated values, falling back to existing values when not provided
            moi = reading_data.get('moi', existing['moi'])
            temp = reading_data.get('temp', existing['temp'])
            humidity = reading_data.get('humidity', existing['humidity'])
            result = reading_data.get('result', existing['result'])
            soil_name = reading_data.get('soil_name', existing.get('soil_name'))

            # Perform update
            cursor.execute(
                """
                UPDATE readings
                SET crop_id = ?, soil_name = ?, growth_stage_id = ?, moi = ?, temp = ?, humidity = ?, result = ?
                WHERE id = ?
                """,
                (crop_id, soil_name, growth_stage_id, moi, temp, humidity, result, reading_id)
            )
            conn.commit()

            # Return updated row with names
            cursor.execute(
                """
                SELECT r.*, c.name AS crop_name, g.name AS growth_stage_name
                FROM readings r
                LEFT JOIN crops c ON r.crop_id = c.id
                LEFT JOIN growth_stages g ON r.growth_stage_id = g.id
                WHERE r.id = ?
                """,
                (reading_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Reading not found after update")
            return dict(row)

    def delete_reading(self, reading_id: int) -> bool:
        """Delete a reading by its numeric id."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM readings WHERE id = ?", (reading_id,))
            conn.commit()
            return cursor.rowcount > 0
