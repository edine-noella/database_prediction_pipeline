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

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database connections on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Include API routes with tags for better organization
app.include_router(
    readings.router,
    prefix="/api",
    # Remove the tags parameter to hide the base endpoints group
    # The individual endpoints will still be visible under their respective tags (SQLite/MongoDB)
)

# Include predictions routes
app.include_router(
    predictions.router,
    prefix="/api",
    tags=["predictions"]
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Crop Monitoring API",
        "docs": "/docs",
        "redoc": "/redoc"
    }