import os
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING, ReturnDocument, server_api
from pymongo.database import Database as MongoDatabase
from pymongo.errors import ConnectionFailure
from datetime import datetime
from dotenv import load_dotenv
from .base import Database

# Load environment variables from .env file
load_dotenv()


def convert_mongo_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB _id to id (string) and remove _id."""
    if not doc:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


class MongoDB(Database):
    def __init__(self, connection_string: str = None, db_name: str = "crop_monitoring"):
        # Get connection string from environment variables if not provided
        connection_string = connection_string or os.getenv(
            "MONGODB_URI", 
            "mongodb://localhost:27017/"
        )
        
        # Create a new client and connect to the server
        try:
            self.client = MongoClient(
                connection_string,
                server_api=server_api.ServerApi('1')
            )
            # Test the connection
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB!")
            
            self.db: MongoDatabase = self.client[db_name]
            self._setup_collections()
            
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

    def _setup_collections(self) -> None:
        """Set up collections and indexes."""
        collections = self.db.list_collection_names()
        if "crops" not in collections:
            self.db.create_collection("crops")
        if "soil_types" not in collections:
            self.db.create_collection("soil_types")
        if "growth_stages" not in collections:
            self.db.create_collection("growth_stages")
        if "readings" not in collections:
            self.db.create_collection("readings")

        # Prefer uniqueness on names for reference collections
        self.db.crops.create_index([("name", ASCENDING)], unique=True)
        self.db.soil_types.create_index([("name", ASCENDING)], unique=True)
        self.db.growth_stages.create_index([("name", ASCENDING)], unique=True)

        # Helpful indexes for readings
        self.db.readings.create_index([("timestamp", DESCENDING)])
        self.db.readings.create_index([("crop_id", ASCENDING)])
        self.db.readings.create_index([("growth_stage_id", ASCENDING)])
        self.db.readings.create_index([("soil_name", ASCENDING)])

    # ----- Lookup helpers -----
    def get_crops(self) -> List[Dict[str, Any]]:
        return [convert_mongo_id(c) for c in self.db.crops.find().sort("_id", 1)]

    def get_soil_types(self) -> List[Dict[str, Any]]:
        return [convert_mongo_id(s) for s in self.db.soil_types.find().sort("_id", 1)]

    def get_growth_stages(self) -> List[Dict[str, Any]]:
        return [convert_mongo_id(g) for g in self.db.growth_stages.find().sort("_id", 1)]

    # ----- Readings -----
    def get_readings(
        self,
        skip: int = 0,
        limit: int = 100,
        reading_id: Optional[str] = None,
        crop_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve readings; `reading_id` can be Mongo _id (string) or legacy numeric id."""
        query: Dict[str, Any] = {}
        if reading_id is not None:
            try:
                query["_id"] = ObjectId(reading_id)
            except Exception:
                # legacy numeric id fallback
                query["id"] = int(reading_id) if isinstance(reading_id, str) and reading_id.isdigit() else reading_id

        if crop_id is not None:
            query["crop_id"] = crop_id

        docs = list(
            self.db.readings.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        )
        if not docs:
            return []

        # Batch resolve names
        crop_ids = {d.get("crop_id") for d in docs if d.get("crop_id")}
        gs_ids = {d.get("growth_stage_id") for d in docs if d.get("growth_stage_id")}

        crops_map: Dict[str, Dict[str, Any]] = {}
        if crop_ids:
            crop_oids = [ObjectId(cid) for cid in crop_ids if isinstance(cid, str) and ObjectId.is_valid(cid)]
            if crop_oids:
                for c in self.db.crops.find({"_id": {"$in": crop_oids}}):
                    crops_map[str(c["_id"])] = c

        gs_map: Dict[str, Dict[str, Any]] = {}
        if gs_ids:
            gs_oids = [ObjectId(gid) for gid in gs_ids if isinstance(gid, str) and ObjectId.is_valid(gid)]
            if gs_oids:
                for g in self.db.growth_stages.find({"_id": {"$in": gs_oids}}):
                    gs_map[str(g["_id"])] = g

        results: List[Dict[str, Any]] = []
        for d in docs:
            out = convert_mongo_id(d)
            cid = out.get("crop_id")
            gid = out.get("growth_stage_id")
            if isinstance(cid, str) and cid in crops_map:
                out["crop_name"] = crops_map[cid].get("name", "Unknown")
            if isinstance(gid, str) and gid in gs_map:
                out["growth_stage_name"] = gs_map[gid].get("name", "Unknown")
            results.append(out)
        return results

    def add_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reading. Stores crop_id and growth_stage_id as stringified ObjectIds.
        Legacy numeric `id` is not assigned for new Mongo records (only present for migrated data)."""
        # Resolve or create crop by name
        crop = self.db.crops.find_one({"name": reading_data["crop_name"]})
        if not crop:
            ins = self.db.crops.insert_one({"name": reading_data["crop_name"]})
            crop = {"_id": ins.inserted_id, "name": reading_data["crop_name"]}

        # Resolve or create growth stage by name
        gs = self.db.growth_stages.find_one({"name": reading_data["growth_stage_name"]})
        if not gs:
            ins = self.db.growth_stages.insert_one({"name": reading_data["growth_stage_name"]})
            gs = {"_id": ins.inserted_id, "name": reading_data["growth_stage_name"]}

        reading_doc: Dict[str, Any] = {
            "crop_id": str(crop["_id"]),
            "growth_stage_id": str(gs["_id"]),
            "soil_name": reading_data["soil_name"],
            "moi": reading_data["moi"],
            "temp": reading_data["temp"],
            "humidity": reading_data["humidity"],
            "result": reading_data.get("result"),  # Default to None if not provided
            "timestamp": datetime.utcnow(),
        }
        ins = self.db.readings.insert_one(reading_doc)
        reading_doc["_id"] = ins.inserted_id

        out = convert_mongo_id(reading_doc)
        out["crop_name"] = crop["name"]
        out["growth_stage_name"] = gs["name"]
        return out

    def update_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a reading by _id (string/ObjectId) or legacy numeric id."""
        # Build filter
        filt: Dict[str, Any] = {}
        if reading_data.get("_id"):
            rid = reading_data["_id"]
            if isinstance(rid, str) and ObjectId.is_valid(rid):
                filt = {"_id": ObjectId(rid)}
            elif isinstance(rid, ObjectId):
                filt = {"_id": rid}
        elif "id" in reading_data:
            filt = {"id": reading_data["id"]}

        if not filt:
            raise ValueError("Reading identifier (_id or id) is required")

        # Build $set
        set_doc: Dict[str, Any] = {}
        for k in ["moi", "temp", "humidity", "result", "soil_name"]:
            if k in reading_data and reading_data[k] is not None:
                set_doc[k] = reading_data[k]

        # Optional relation updates by name
        if reading_data.get("crop_name"):
            crop = self.db.crops.find_one({"name": reading_data["crop_name"]})
            if not crop:
                ins = self.db.crops.insert_one({"name": reading_data["crop_name"]})
                crop = {"_id": ins.inserted_id, "name": reading_data["crop_name"]}
            set_doc["crop_id"] = str(crop["_id"])

        if reading_data.get("growth_stage_name"):
            gs = self.db.growth_stages.find_one({"name": reading_data["growth_stage_name"]})
            if not gs:
                ins = self.db.growth_stages.insert_one({"name": reading_data["growth_stage_name"]})
                gs = {"_id": ins.inserted_id, "name": reading_data["growth_stage_name"]}
            set_doc["growth_stage_id"] = str(gs["_id"])

        if not set_doc:
            doc = self.db.readings.find_one(filt)
            if not doc:
                raise ValueError("Reading not found")
            # Enrich and return
            out = convert_mongo_id(doc)
            # Try enrich
            try:
                if out.get("crop_id") and ObjectId.is_valid(out["crop_id"]):
                    crop = self.db.crops.find_one({"_id": ObjectId(out["crop_id"])})
                    if crop:
                        out["crop_name"] = crop.get("name")
                if out.get("growth_stage_id") and ObjectId.is_valid(out["growth_stage_id"]):
                    gs = self.db.growth_stages.find_one({"_id": ObjectId(out["growth_stage_id"])})
                    if gs:
                        out["growth_stage_name"] = gs.get("name")
            except Exception:
                pass
            return out

        updated = self.db.readings.find_one_and_update(
            filt,
            {"$set": set_doc},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise ValueError("Reading not found")

        out = convert_mongo_id(updated)
        # Enrich
        try:
            if out.get("crop_id") and ObjectId.is_valid(out["crop_id"]):
                crop = self.db.crops.find_one({"_id": ObjectId(out["crop_id"])})
                if crop:
                    out["crop_name"] = crop.get("name")
            if out.get("growth_stage_id") and ObjectId.is_valid(out["growth_stage_id"]):
                gs = self.db.growth_stages.find_one({"_id": ObjectId(out["growth_stage_id"])})
                if gs:
                    out["growth_stage_name"] = gs.get("name")
        except Exception:
            pass
        return out

    def delete_reading(self, reading_id: Any) -> bool:
        """Delete a reading by _id (string/ObjectId) or legacy numeric id."""
        filt: Dict[str, Any] = {}
        if isinstance(reading_id, str) and ObjectId.is_valid(reading_id):
            filt = {"_id": ObjectId(reading_id)}
        elif isinstance(reading_id, int) or (isinstance(reading_id, str) and reading_id.isdigit()):
            filt = {"id": int(reading_id)}
        else:
            # last resort; attempt direct match
            filt = {"_id": reading_id}

        res = self.db.readings.delete_one(filt)
        return res.deleted_count > 0

    def close(self) -> None:
        self.client.close()

