from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Union
import os
import sys
from bson import ObjectId
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from bson import ObjectId

# Import database dependencies
from ..database.database import get_db
from ..database import get_database
from ..database.base import Database

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Try to import Keras
try:
    import keras
    _keras_available = True
except ImportError:
    _keras_available = False

router = APIRouter(tags=["predictions"])

# Define request/response models
class PredictionRequest(BaseModel):
    """Request model for making a prediction"""
    moi: float
    temp: float
    humidity: float
    crop_name: str
    soil_name: str
    growth_stage_name: str

class PredictionResponse(BaseModel):
    """Response model for prediction results"""
    status: str
    features: Dict[str, Any]
    prediction: List[float]
    predicted_class: int
    class_name: str
    reading: Optional[Dict[str, Any]] = None

# Load model artifacts
MODELS_DIR = os.path.join(project_root, "models")

# Load model artifacts once at startup
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
models_dir = os.path.join(project_root, "models")

# Initialize model artifacts as None
model = None
scaler = None
columns = None

def load_artifacts():
    """Load model, scaler, and columns (cached after first load)"""
    global model, scaler, columns
    
    if model is None or scaler is None or columns is None:
        try:
            # Load model
            model_path = os.path.join(models_dir, "model.keras")
            if not os.path.exists(model_path):
                model_path = os.path.join(models_dir, "neural_network_model.h5")
            
            if not _keras_available:
                raise ImportError("Keras is not installed. Install with: pip install 'keras>=3,<4'")
                
            model = keras.models.load_model(model_path)
            
            # Load scaler and columns
            with open(os.path.join(models_dir, "scaler.pkl"), 'rb') as f:
                scaler = pickle.load(f)
            with open(os.path.join(models_dir, "columns.pkl"), 'rb') as f:
                columns = pickle.load(f)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading model artifacts: {str(e)}")
    
    return model, scaler, columns

def prepare_features(request: PredictionRequest, columns: List[str]) -> pd.DataFrame:
    """Prepare features for prediction"""
    input_data = {
        'moi': request.moi,
        'temp': request.temp,
        'humidity': request.humidity,
    }
    
    # Add one-hot encoded features
    for col in columns:
        if col.startswith('crop ID_') and col.endswith(f'_{request.crop_name}'):
            input_data[col] = 1.0
        elif col.startswith('soil_type_') and col.endswith(f'_{request.soil_name}'):
            input_data[col] = 1.0
        elif col.startswith('Seedling Stage_') and col.endswith(f'_{request.growth_stage_name}'):
            input_data[col] = 1.0
    
    # Create feature DataFrame with all zeros first
    features = pd.DataFrame(0, index=[0], columns=columns)
    
    # Update with actual values
    for col in input_data:
        if col in features.columns:
            features[col] = input_data[col]
    
    return features

@router.post("/predict", response_model=PredictionResponse, summary="Make a prediction with provided data", include_in_schema=False)
async def make_prediction(request: PredictionRequest):
    """
    Make a prediction using the trained model with provided data.
    
    This endpoint takes sensor readings and returns a prediction
    of whether irrigation is needed.
    """
    try:
        # Get model artifacts (cached after first load)
        model, scaler, columns = load_artifacts()
        
        # Prepare features
        features = prepare_features(request, columns)
        
        # Scale features
        scaled_features = scaler.transform(features)
        
        # Make prediction with verbose=0 to suppress output
        prediction = model.predict(scaled_features, verbose=0)
        
        # Convert prediction to a numpy array if it's not already
        prediction = np.array(prediction)
        
        # Handle different prediction output formats
        if prediction.ndim > 1 and prediction.shape[1] > 2:
            # If we have more than 2 classes, take the first two
            prediction = prediction[:, :2]
        
        # Get the predicted class (0 or 1)
        if prediction.ndim > 1 and prediction.shape[1] > 1:
            # For multi-class prediction
            predicted_class = int(np.argmax(prediction[0]))
            # Ensure we only have 2 probabilities
            probs = prediction[0][:2].tolist()
        else:
            # For binary prediction
            predicted_class = int(prediction[0] > 0.5)
            probs = [1.0 - prediction[0], float(prediction[0])]
        
        # Prepare response
        return {
            "status": "success",
            "features": {col: float(features.iloc[0][col]) for col in columns},
            "prediction": probs,
            "predicted_class": predicted_class,
            "class_name": "Irrigation Needed" if predicted_class == 1 else "No Irrigation Needed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predict/latest/sqlite", response_model=PredictionResponse, tags=["predictions"])
async def predict_latest_sqlite():
    """
    Make a prediction using the latest reading from SQLite database.
    
    Fetches the most recent reading from SQLite, uses it to make a prediction,
    and saves the prediction result back to the database.
    """
    try:
        # Get model artifacts (cached after first load)
        model, scaler, columns = load_artifacts()
        db = get_database('sqlite')
        
        # Always fetch the latest reading from database
        latest_readings = db.get_readings(limit=1)
        if not latest_readings:
            raise HTTPException(status_code=404, detail="No readings found in SQLite database")
        
        latest_reading = latest_readings[0]
        reading_id = latest_reading.get('id')
        
        request = PredictionRequest(
            moi=latest_reading.get('moi'),
            temp=latest_reading.get('temp'),
            humidity=latest_reading.get('humidity'),
            crop_name=latest_reading.get('crop_name', 'unknown'),
            soil_name=latest_reading.get('soil_name', 'unknown'),
            growth_stage_name=latest_reading.get('growth_stage_name', 'unknown')
        )
        
        # Prepare features
        features = prepare_features(request, columns)
        
        # Scale features
        scaled_features = scaler.transform(features)
        
        # Make prediction with verbose=0 to suppress output
        prediction = model.predict(scaled_features, verbose=0)
        
        # Convert prediction to a numpy array if it's not already
        prediction = np.array(prediction)
        
        # Handle different prediction output formats
        if prediction.ndim > 1 and prediction.shape[1] > 2:
            # If we have more than 2 classes, take the first two
            prediction = prediction[:, :2]
        
        # Get the predicted class (0 or 1)
        if prediction.ndim > 1 and prediction.shape[1] > 1:
            # For multi-class prediction
            predicted_class = int(np.argmax(prediction[0]))
            # Ensure we only have 2 probabilities
            probs = prediction[0][:2].tolist()
        else:
            # For binary prediction
            predicted_class = int(prediction[0] > 0.5)
            probs = [1.0 - prediction[0], float(prediction[0])]
        
        # Save prediction result back to the database
        try:
            # Update the reading with prediction result
            update_data = {
                'id': reading_id,  # Include the ID in the update data
                'result': predicted_class,
                'prediction_probability': float(probs[1]) if len(probs) > 1 else float(probs[0]),
                'prediction_timestamp': datetime.utcnow().isoformat(),
                'crop_name': latest_reading.get('crop_name', ''),
                'growth_stage_name': latest_reading.get('growth_stage_name', ''),
                'moi': latest_reading.get('moi'),
                'temp': latest_reading.get('temp'),
                'humidity': latest_reading.get('humidity'),
                'soil_name': latest_reading.get('soil_name', '')
            }
            try:
                # Pass the complete update data dictionary as a single argument
                updated_reading = db.update_reading(update_data)
                if updated_reading:
                    latest_reading = updated_reading
            except Exception as e:
                print(f"Error updating reading: {e}")
        except Exception as e:
            print(f"Warning: Could not update reading with prediction result: {e}")
            # Log the full error for debugging
            import traceback
            traceback.print_exc()
        
        # Prepare response
        return {
            "status": "success",
            "features": {col: float(features.iloc[0][col]) for col in columns},
            "prediction": probs,
            "predicted_class": predicted_class,
            "class_name": "Irrigation Needed" if predicted_class == 1 else "No Irrigation Needed",
            "reading": latest_reading
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predict/latest/mongodb", response_model=PredictionResponse, tags=["predictions"])
async def predict_latest_mongodb():
    """
    Make a prediction using the latest reading from MongoDB.
    
    Fetches the most recent reading from MongoDB, uses it to make a prediction,
    and saves the prediction result back to the database.
    """
    try:
        # Get model artifacts (cached after first load)
        model, scaler, columns = load_artifacts()
        db = get_database('mongodb')
        
        # Always fetch the latest reading from database
        latest_readings = db.get_readings(limit=1)
        if not latest_readings:
            raise HTTPException(status_code=404, detail="No readings found in MongoDB")
        
        latest_reading = latest_readings[0]
        reading_id = latest_reading.get('_id', latest_reading.get('id'))
        
        request = PredictionRequest(
            moi=latest_reading.get('moi'),
            temp=latest_reading.get('temp'),
            humidity=latest_reading.get('humidity'),
            crop_name=latest_reading.get('crop_name', 'unknown'),
            soil_name=latest_reading.get('soil_name', 'unknown'),
            growth_stage_name=latest_reading.get('growth_stage_name', 'unknown')
        )
        
        # Prepare features
        features = prepare_features(request, columns)
        
        # Scale features
        scaled_features = scaler.transform(features)
        
        # Make prediction with verbose=0 to suppress output
        prediction = model.predict(scaled_features, verbose=0)
        
        # Convert prediction to a numpy array if it's not already
        prediction = np.array(prediction)
        
        # Handle different prediction output formats
        if prediction.ndim > 1 and prediction.shape[1] > 2:
            # If we have more than 2 classes, take the first two
            prediction = prediction[:, :2]
        
        # Get the predicted class (0 or 1)
        if prediction.ndim > 1 and prediction.shape[1] > 1:
            # For multi-class prediction
            predicted_class = int(np.argmax(prediction[0]))
            # Ensure we only have 2 probabilities
            probs = prediction[0][:2].tolist()
        else:
            # For binary prediction
            predicted_class = int(prediction[0] > 0.5)
            probs = [1.0 - prediction[0], float(prediction[0])]
        
        # Save prediction result back to the database
        try:
            # For MongoDB, we need to handle the update differently than SQLite
            update_data = {
                'result': predicted_class,
                'prediction_probability': float(probs[1]) if len(probs) > 1 else float(probs[0]),
                'prediction_timestamp': datetime.utcnow().isoformat(),
                'crop_name': latest_reading.get('crop_name', ''),
                'growth_stage_name': latest_reading.get('growth_stage_name', ''),
                'moi': latest_reading.get('moi'),
                'temp': latest_reading.get('temp'),
                'humidity': latest_reading.get('humidity'),
                'soil_name': latest_reading.get('soil_name', '')
            }
            
            def convert_id(document: Union[Dict[str, Any], None]) -> Dict[str, Any]:
                """Convert MongoDB _id to id and make it a string"""
                if not document:
                    return {}
                if '_id' in document:
                    document['id'] = str(document.pop('_id'))
                return document

            # Handle MongoDB update
            if hasattr(db, 'db') and hasattr(db.db, 'name') and db.db.name == 'crop_monitoring':
                try:
                    from bson.objectid import ObjectId
                    
                    # Ensure we have a valid ObjectId
                    obj_id = ObjectId(str(reading_id)) if not isinstance(reading_id, ObjectId) else reading_id
                    
                    # Update the document using the database instance
                    result = db.db.readings.update_one(
                        {"_id": obj_id},
                        {"$set": update_data}
                    )
                    
                    if result.modified_count > 0:
                        # Get the updated document
                        updated_doc = db.db.readings.find_one({"_id": obj_id})
                        if updated_doc:
                            latest_reading = convert_id(updated_doc)
                            # Ensure all expected fields are present
                            for field in ['crop_name', 'growth_stage_name', 'soil_name']:
                                if field not in latest_reading and field in update_data:
                                    latest_reading[field] = update_data[field]
                    else:
                        print(f"No documents were modified. Document with _id {obj_id} may not exist.")
                        
                except Exception as e:
                    print(f"Error updating MongoDB document: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # Handle SQLite update - include ID in the update data
                update_data_with_id = update_data.copy()
                update_data_with_id['id'] = reading_id
                try:
                    updated_reading = db.update_reading(update_data_with_id)
                    if updated_reading:
                        latest_reading = updated_reading
                except Exception as e:
                    print(f"Error updating SQLite document: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"Warning: Could not update reading with prediction result: {e}")
            # Log the full error for debugging
            import traceback
            traceback.print_exc()
        
        # Prepare response
        return {
            "status": "success",
            "features": {col: float(features.iloc[0][col]) for col in columns},
            "prediction": probs,
            "predicted_class": predicted_class,
            "class_name": "Irrigation Needed" if predicted_class == 1 else "No Irrigation Needed",
            "reading": latest_reading
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
