import argparse
import os
import sys
import json
from typing import Dict, Any, List

import requests
import numpy as np
import pandas as pd
import pickle

# Try to import standalone Keras (>=3) and TensorFlow Keras; both optional
try:
    import keras  # type: ignore
    _keras_load_model = keras.models.load_model  # type: ignore
except Exception:
    keras = None  # type: ignore
    _keras_load_model = None  # type: ignore

try:
    from tensorflow.keras.models import load_model as _tf_load_model  # type: ignore
except Exception:
    _tf_load_model = None  # type: ignore

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

COLUMNS_PKL = os.path.join(MODELS_DIR, "columns.pkl")
SCALER_PKL = os.path.join(MODELS_DIR, "scaler.pkl")
MODEL_H5 = os.path.join(MODELS_DIR, "neural_network_model.h5")
# Prefer native Keras format if present (support two common filenames)
MODEL_KERAS_PRIMARY = os.path.join(MODELS_DIR, "model.keras")
MODEL_KERAS_ALT = os.path.join(MODELS_DIR, "nn_model.keras")
SK_MODEL_PKL = os.path.join(MODELS_DIR, "sklearn_model.pkl")


def fetch_latest_reading(base_url: str, source: str) -> Dict[str, Any]:
    """Fetch the latest reading from the API.

    Args:
        base_url: Base URL of the API, e.g. http://127.0.0.1:8000
        source: "mongodb" or "sqlite"
    Returns:
        A dict representing a single reading.
    Raises:
        RuntimeError if request fails or response unexpected.
    """
    url = f"{base_url.rstrip('/')}/api/{source}?limit=1"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch readings: {resp.status_code} {resp.text}")
    data = resp.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError("No readings returned by API")
    return data[0]


def load_artifacts():
    """Load columns, scaler, and model.

    Preference order:
    1) scikit-learn model at models/sklearn_model.pkl
    2) TensorFlow .h5 model at models/neural_network_model.h5 (requires tensorflow)
    """
    if not os.path.exists(COLUMNS_PKL):
        raise FileNotFoundError(f"Missing columns.pkl at {COLUMNS_PKL}")
    if not os.path.exists(SCALER_PKL):
        raise FileNotFoundError(f"Missing scaler.pkl at {SCALER_PKL}")

    with open(COLUMNS_PKL, "rb") as f:
        columns: List[str] = pickle.load(f)
    with open(SCALER_PKL, "rb") as f:
        scaler = pickle.load(f)
    model = None
    model_type = None

    if os.path.exists(SK_MODEL_PKL):
        with open(SK_MODEL_PKL, "rb") as f:
            model = pickle.load(f)
        model_type = "sklearn"
    elif os.path.exists(MODEL_KERAS_PRIMARY) or os.path.exists(MODEL_KERAS_ALT):
        # Load native Keras format first (.keras)
        keras_path = MODEL_KERAS_PRIMARY if os.path.exists(MODEL_KERAS_PRIMARY) else MODEL_KERAS_ALT
        load_errors = []
        if _keras_load_model is None:
            raise RuntimeError("Keras is not installed but a .keras file exists. Install with: pip install 'keras>=3,<4'")
        for kwargs in ({}, {"compile": False}, {"compile": False, "safe_mode": False}):
            try:
                model = _keras_load_model(keras_path, **kwargs)
                model_type = "keras3"
                break
            except Exception as e:
                load_errors.append(f"keras.load_model({kwargs}) error: {e}")
        if model is None:
            raise RuntimeError(
                "Unable to load model file " + os.path.basename(keras_path) + ".\n" + "\n".join(load_errors)
            )
    elif os.path.exists(MODEL_H5):
        # Try H5 (standalone Keras first, then tf.keras)
        load_errors = []
        if _keras_load_model is not None:
            try:
                model = _keras_load_model(MODEL_H5)
                model_type = "keras3"
            except Exception as e1:
                try:
                    model = _keras_load_model(MODEL_H5, compile=False)
                    model_type = "keras3"
                except Exception as e2:
                    try:
                        model = _keras_load_model(MODEL_H5, compile=False, safe_mode=False)
                        model_type = "keras3"
                    except Exception as e3:
                        load_errors.append(
                            f"keras.load_model error: {e1}; then compile=False error: {e2}; then safe_mode=False error: {e3}"
                        )
                        model = None
        if model is None and _tf_load_model is not None:
            try:
                model = _tf_load_model(MODEL_H5)
                model_type = "tf.keras"
            except Exception as e1:
                try:
                    model = _tf_load_model(MODEL_H5, compile=False)
                    model_type = "tf.keras"
                except Exception as e2:
                    load_errors.append(f"tf.keras.load_model error: {e1}; then compile=False error: {e2}")
                    model = None
        if model is None:
            raise RuntimeError(
                "Unable to load model file models/neural_network_model.h5.\n" +
                "\n".join(load_errors) +
                "\nTip: Re-save the model as native Keras (.keras) or provide sklearn_model.pkl."
            )
    else:
        raise FileNotFoundError(
            "No model found. Provide models/model.keras (preferred), models/sklearn_model.pkl, or models/neural_network_model.h5"
        )

    return columns, scaler, model, model_type


essential_numeric_fields = [
    "moi",
    "temp",
    "humidity",
]


def build_feature_frame(reading: Dict[str, Any], columns: List[str]) -> pd.DataFrame:
    """Build a DataFrame with one row matching the expected columns order.

    - If a feature is missing in reading, fill with 0.
    - Cast booleans True/False to 1/0.
    - Cast strings that look numeric to float, else leave 0.
    """
    row: Dict[str, Any] = {}

    # Start with zeros for all columns
    for col in columns:
        row[col] = 0.0

    # Map known numeric fields if present
    for key in essential_numeric_fields:
        if key in reading and key in columns:
            try:
                row[key] = float(reading[key])
            except Exception:
                row[key] = 0.0

    # Attempt to map any remaining overlapping numeric keys
    for col in columns:
        if col not in essential_numeric_fields and col in reading:
            val = reading[col]
            # Try to coerce to number
            try:
                if isinstance(val, bool):
                    row[col] = 1.0 if val else 0.0
                elif isinstance(val, (int, float, np.number)):
                    row[col] = float(val)
                elif isinstance(val, str):
                    row[col] = float(val) if val.replace('.', '', 1).isdigit() else row[col]
            except Exception:
                pass

    df = pd.DataFrame([row], columns=columns)
    return df


def predict_from_reading(base_url: str, source: str) -> Dict[str, Any]:
    # Get the latest reading directly without any input prompt
    reading = fetch_latest_reading(base_url, source)
    print(f"Using latest record from {source} with timestamp: {reading.get('timestamp')}")
    
    columns, scaler, model, model_type = load_artifacts()
    X = build_feature_frame(reading, columns)
    X_scaled = scaler.transform(X)

    # Make prediction
    if model_type == "sklearn":
        y_pred = model.predict(X_scaled)
    else:  # keras
        y_pred = model.predict(X_scaled)

    # Format prediction output
    pred = y_pred[0] if hasattr(y_pred, 'shape') and y_pred.shape == (1, 1) else y_pred
    if hasattr(pred, "tolist"):
        pred = pred.tolist()

    # Prepare the result
    result = {
        "status": "success",
        "prediction": pred,
        "model_type": model_type,
        "record_id": str(reading.get('_id', reading.get('id', 'unknown'))),
        "timestamp": reading.get('timestamp')
    }
    
    # Add sensor values if available
    for field in ['moi', 'temp', 'humidity']:
        if field in reading:
            result[field] = reading[field]
            
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch latest reading via API and run model prediction")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"), help="Base URL for the API")
    parser.add_argument("--source", choices=["mongodb", "sqlite"], default=os.environ.get("API_SOURCE", "mongodb"), help="Data source endpoint")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    try:
        result = predict_from_reading(args.base_url, args.source)
        if args.pretty:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(json.dumps(result, default=str))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
