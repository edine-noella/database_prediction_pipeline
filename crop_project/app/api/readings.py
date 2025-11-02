from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Union
from datetime import datetime
from bson import ObjectId
from ..database.base import Database
from ..database import schemas
from .deps import get_db, get_mongodb

# Create the router
router = APIRouter()

# Helper function to convert DB objects to dict
def row_to_dict(row):
    if hasattr(row, "__table__"):  # SQLAlchemy model
        return {c.name: getattr(row, c.name) for c in row.__table__.columns}
    return dict(row)  # Already a dict from MongoDB

# SQLite Endpoints
@router.post(
    "/sqlite", 
    response_model=schemas.Reading, 
    tags=["SQLite"],
    operation_id="create_reading_sqlite"
)
async def create_reading_sqlite(reading: schemas.ReadingCreate, db: Database = Depends(get_db)):
    try:
        reading_dict = reading.dict()
        if "timestamp" in reading_dict and reading_dict["timestamp"] is None:
            reading_dict["timestamp"] = datetime.utcnow().isoformat()
        return db.add_reading(reading_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/sqlite", 
    response_model=List[schemas.Reading], 
    tags=["SQLite"],
    operation_id="list_readings_sqlite"
)
async def read_readings_sqlite(
    skip: int = 0,
    limit: int = 100,
    crop_id: Optional[int] = None,
    db: Database = Depends(get_db)
):
    try:
        return db.get_readings(skip=skip, limit=limit, crop_id=crop_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/sqlite/{reading_id}", 
    response_model=schemas.Reading, 
    tags=["SQLite"],
    operation_id="get_reading_sqlite"
)
async def read_reading_sqlite(reading_id: int, db: Database = Depends(get_db)):
    readings = db.get_readings(reading_id=reading_id)
    if not readings:
        raise HTTPException(status_code=404, detail="Reading not found")
    return readings[0]

@router.put(
    "/sqlite/{reading_id}", 
    response_model=schemas.Reading, 
    tags=["SQLite"],
    operation_id="update_reading_sqlite"
)
async def update_reading_sqlite(
    reading_id: int,
    reading: schemas.ReadingCreate,
    db: Database = Depends(get_db)
):
    try:
        existing = db.get_readings(reading_id=reading_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Reading not found")
        reading_dict = reading.dict()
        reading_dict["id"] = reading_id
        return db.update_reading(reading_dict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/sqlite/{reading_id}", 
    response_model=dict, 
    tags=["SQLite"],
    operation_id="delete_reading_sqlite"
)
async def delete_reading_sqlite(reading_id: int, db: Database = Depends(get_db)):
    try:
        success = db.delete_reading(reading_id)
        if not success:
            raise HTTPException(status_code=404, detail="Reading not found")
        return {"status": "success", "message": f"Reading {reading_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# MongoDB Endpoints
@router.post(
    "/mongodb", 
    response_model=schemas.Reading, 
    tags=["MongoDB"],
    operation_id="create_reading_mongodb"
)
async def create_reading_mongodb(reading: schemas.ReadingCreate, db: Database = Depends(get_mongodb)):
    try:
        reading_dict = reading.dict()
        if "timestamp" in reading_dict and reading_dict["timestamp"] is None:
            reading_dict["timestamp"] = datetime.utcnow().isoformat()
        return db.add_reading(reading_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/mongodb", 
    response_model=List[schemas.Reading], 
    tags=["MongoDB"],
    operation_id="list_readings_mongodb"
)
async def read_readings_mongodb(
    skip: int = 0,
    limit: int = 100,
    crop_id: Optional[Union[int, str]] = None,
    db: Database = Depends(get_mongodb)
):
    try:
        return db.get_readings(skip=skip, limit=limit, crop_id=crop_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/mongodb/{reading_id}", 
    response_model=schemas.Reading, 
    tags=["MongoDB"],
    operation_id="get_reading_mongodb"
)
async def read_reading_mongodb(reading_id: str, db: Database = Depends(get_mongodb)):
    try:
        if not ObjectId.is_valid(reading_id):
            raise HTTPException(status_code=400, detail="Invalid reading ID format")
            
        readings = db.get_readings(reading_id=reading_id)
        if not readings:
            raise HTTPException(status_code=404, detail="Reading not found")
        return readings[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/mongodb/{reading_id}", 
    response_model=schemas.Reading, 
    tags=["MongoDB"],
    operation_id="update_reading_mongodb"
)
async def update_reading_mongodb(
    reading_id: str,
    reading: schemas.ReadingCreate,
    db: Database = Depends(get_mongodb)
):
    try:
        if not ObjectId.is_valid(reading_id):
            raise HTTPException(status_code=400, detail="Invalid reading ID format")
            
        # Get the existing reading to ensure it exists
        existing_readings = db.get_readings(reading_id=reading_id)
        if not existing_readings or not existing_readings[0]:
            raise HTTPException(status_code=404, detail="Reading not found")
            
        # Convert the reading to a dict and include the ID
        reading_dict = reading.dict()
        reading_dict['_id'] = reading_id  # Use _id for MongoDB
        
        # Remove None values
        reading_dict = {k: v for k, v in reading_dict.items() if v is not None}
        
        try:
            # Update the reading - this now returns the updated document
            updated_reading = db.update_reading(reading_dict)
            return updated_reading
        except ValueError as e:
            if "not found" in str(e).lower():
                raise HTTPException(status_code=404, detail=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_detail = f"{str(e)}\n\n{traceback.format_exc()}"
        print(f"Error updating reading: {error_detail}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/mongodb/{reading_id}", 
    response_model=dict, 
    tags=["MongoDB"],
    operation_id="delete_reading_mongodb"
)
async def delete_reading_mongodb(reading_id: str, db: Database = Depends(get_mongodb)):
    try:
        if not ObjectId.is_valid(reading_id):
            raise HTTPException(status_code=400, detail="Invalid reading ID format")
            
        success = db.delete_reading(reading_id)
        if not success:
            raise HTTPException(status_code=404, detail="Reading not found")
        return {"status": "success", "message": f"Reading {reading_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
