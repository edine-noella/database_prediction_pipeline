from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import readings, predictions
from .database import init_db


# Initialize FastAPI app
app = FastAPI(
    title="Crop Monitoring API",
    description="API for managing crop monitoring data with support for both SQLite and MongoDB",
    version="1.0.0",
)
