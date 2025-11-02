import pandas as pd
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import engine, Base
from app.database.models import Crop, SoilType, GrowthStage, Reading

# Create the tables
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Load the data
df = pd.read_csv('data/cropdata_updated.csv')

# Get unique values for lookup tables
crops = df['crop ID'].unique()
soil_types = df['soil_type'].unique()
growth_stages = df['Seedling Stage'].unique()

# Populate lookup tables and create mapping
crop_map = {}
for crop_name in crops:
    crop = Crop(name=crop_name)
    db.add(crop)
    db.commit()
    db.refresh(crop)
    crop_map[crop_name] = crop.id

soil_type_map = {}
for soil_type_name in soil_types:
    soil_type = SoilType(name=soil_type_name)
    db.add(soil_type)
    db.commit()
    db.refresh(soil_type)
    soil_type_map[soil_type_name] = soil_type.id

growth_stage_map = {}
for growth_stage_name in growth_stages:
    growth_stage = GrowthStage(name=growth_stage_name)
    db.add(growth_stage)
    db.commit()
    db.refresh(growth_stage)
    growth_stage_map[growth_stage_name] = growth_stage.id

# Populate the readings table
for _, row in df.iterrows():
    reading = Reading(
        crop_id=crop_map[row['crop ID']],
        soil_type_id=soil_type_map[row['soil_type']],
        growth_stage_id=growth_stage_map[row['Seedling Stage']],
        moi=row['MOI'],
        temp=row['temp'],
        humidity=row['humidity'],
        result=row['result']
    )
    db.add(reading)

db.commit()
db.close()

print("Data loaded successfully!")
