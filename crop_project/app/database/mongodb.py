import os
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import Union, Dict, Any

# Load environment variables
load_dotenv()

# MongoDB connection string
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client["crop_monitoring"]

# Collections
crops_collection = db["crops"]
soil_types_collection = db["soil_types"]
growth_stages_collection = db["growth_stages"]
readings_collection = db["readings"]
logs_collection = db["logs"]

def convert_id(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert _id to id and make it a string"""
    if document and '_id' in document:
        document['id'] = str(document.pop('_id'))
    return document

def convert_id_list(documents: list) -> list:
    """Convert _id to id for a list of documents"""
    return [convert_id(doc) for doc in documents] if documents else []

def init_mongodb():
    """Initialize MongoDB with indexes and any required setup"""
    # Drop any legacy unique indexes on 'id' that may exist from earlier versions
    def _drop_legacy_id_index(col):
        try:
            info = col.index_information()
            for name, meta in info.items():
                # meta['key'] is a list like [('id', 1)]
                if meta.get('key') == [('id', 1)]:
                    col.drop_index(name)
        except Exception:
            # Safe best-effort; continue creating current indexes
            pass

    for col in [crops_collection, soil_types_collection, growth_stages_collection, readings_collection]:
        _drop_legacy_id_index(col)

    # Create indexes for better query performance
    crops_collection.create_index("name", unique=True)
    soil_types_collection.create_index("name", unique=True)
    growth_stages_collection.create_index("name", unique=True)
    
    # Create index for common queries on readings
    readings_collection.create_index("crop_id")
    readings_collection.create_index("timestamp")
    
    print("MongoDB initialized with indexes")

def clear_collections():
    """Clear all collections (for testing/development)"""
    crops_collection.delete_many({})
    soil_types_collection.delete_many({})
    growth_stages_collection.delete_many({})
    readings_collection.delete_many({})
    logs_collection.delete_many({})
    print("All collections cleared")

class MongoDB:
    """MongoDB database operations for crop monitoring"""
    
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client["crop_monitoring"]
        self.readings = self.db["readings"]
        self.crops = self.db["crops"]
        self.growth_stages = self.db["growth_stages"]
    
    def close(self):
        """Close the MongoDB connection"""
        self.client.close()
    
    def get_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get readings with optional limit"""
        cursor = self.readings.find().sort("timestamp", -1).limit(limit)
        return [convert_id(doc) for doc in cursor]
    
    def add_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new reading"""
        # Get or create crop
        crop = self.crops.find_one({"name": reading_data['crop_name']})
        if not crop:
            crop_id = self.crops.insert_one({"name": reading_data['crop_name']}).inserted_id
        else:
            crop_id = crop['_id']
        
        # Get or create growth stage
        growth_stage = self.growth_stages.find_one({"name": reading_data['growth_stage_name']})
        if not growth_stage:
            growth_stage_id = self.growth_stages.insert_one({"name": reading_data['growth_stage_name']}).inserted_id
        else:
            growth_stage_id = growth_stage['_id']
        
        # Prepare reading document
        reading_doc = {
            "crop_id": crop_id,
            "crop_name": reading_data['crop_name'],
            "growth_stage_id": growth_stage_id,
            "growth_stage_name": reading_data['growth_stage_name'],
            "soil_name": reading_data['soil_name'],
            "moi": reading_data['moi'],
            "temp": reading_data['temp'],
            "humidity": reading_data['humidity'],
            "result": reading_data.get('result'),  # Default to None if not provided
            "timestamp": reading_data.get('timestamp', datetime.utcnow())
        }
        
        # Insert reading
        result = self.readings.insert_one(reading_doc)
        reading_doc['_id'] = result.inserted_id
        return convert_id(reading_doc)
    
    def update_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing reading with new data
        
        Args:
            reading_data: Dictionary containing the reading data including 'id' or '_id'
            
        Returns:
            Dict: The updated reading document
        """
        try:
            from bson.objectid import ObjectId
            
            # Get the reading ID from the input data
            reading_id = reading_data.get('_id') or reading_data.get('id')
            if not reading_id:
                raise ValueError("Reading ID is required in the input data")
                
            # Convert string ID to ObjectId if it's a valid ObjectId string
            if isinstance(reading_id, str) and ObjectId.is_valid(reading_id):
                obj_id = ObjectId(reading_id)
                query = {"_id": obj_id}
            else:
                query = {"$or": [{"_id": reading_id}, {"id": reading_id}]}
            
            # Remove None values and ID fields from update data
            update_data = {k: v for k, v in reading_data.items() 
                         if v is not None and k not in ('_id', 'id')}
            
            if not update_data:
                # If no fields to update, just return the current document
                return self.readings.find_one(query)
            
            # Update the document and return the updated version
            result = self.readings.find_one_and_update(
                query,
                {"$set": update_data},
                return_document=True
            )
            
            if not result:
                raise ValueError("Reading not found")
                
            # Convert ObjectId to string for JSON serialization
            result['_id'] = str(result['_id'])
            return result
            
        except Exception as e:
            print(f"Error updating reading: {e}")
            raise
