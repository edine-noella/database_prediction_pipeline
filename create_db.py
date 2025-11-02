import sys
import os

# Add the project root to the Python path to allow for correct module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.database import engine, Base
from app.database import models

def create_database():
    """
    Creates all the tables in the database based on the SQLAlchemy models.
    """
    print("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    create_database()
