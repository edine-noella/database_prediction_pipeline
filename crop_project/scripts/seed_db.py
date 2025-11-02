import sys
import os
from sqlalchemy.orm import Session

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.database import engine, SessionLocal
from app.database import models

def seed_data():
    """
    Creates database tables and populates them with initial data for crops, 
    soil types, and growth stages.
    """
    # Create tables first
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db: Session = SessionLocal()
    try:
        # Check if data already exists
        if db.query(models.Crop).count() > 0:
            print("Data already exists. Skipping seeding.")
            return

        print("Seeding database with initial data...")

        # Create sample data
        crop1 = models.Crop(name="Corn")
        crop2 = models.Crop(name="Wheat")

        soil1 = models.SoilType(name="Loam")
        soil2 = models.SoilType(name="Clay")

        stage1 = models.GrowthStage(name="Vegetative")
        stage2 = models.GrowthStage(name="Flowering")

        # Add to session and commit
        db.add_all([crop1, crop2, soil1, soil2, stage1, stage2])
        db.commit()

        print("Database seeded successfully.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
