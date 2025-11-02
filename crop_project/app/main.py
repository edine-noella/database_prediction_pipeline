from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import readings, predictions
from .database import init_db
