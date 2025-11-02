from pydantic import BaseModel
from datetime import datetime

class ReadingBase(BaseModel):
    moi: float
    temp: float
    humidity: float
    soil_name: str  # Added soil_name to base

class ReadingCreate(ReadingBase):
    crop_name: str
    growth_stage_name: str
    # Removed soil_type_name as it's now part of the base

class Reading(ReadingBase):
    id: int | str
    crop_id: int | str
    crop_name: str
    growth_stage_id: int | str
    growth_stage_name: str
    timestamp: datetime | None = None
    result: int | str | None = None
    
    class Config:
        from_attributes = True

class CropBase(BaseModel):
    name: str

class CropCreate(CropBase):
    pass

class Crop(CropBase):
    id: int | str
    readings: list[Reading] = []

    class Config:
        from_attributes = True

class SoilTypeBase(BaseModel):
    name: str

class SoilTypeCreate(SoilTypeBase):
    pass

class SoilType(SoilTypeBase):
    id: int | str
    # Removed readings relationship as we're now using soil_name directly

    class Config:
        from_attributes = True

class GrowthStageBase(BaseModel):
    name: str

class GrowthStageCreate(GrowthStageBase):
    pass

class GrowthStage(GrowthStageBase):
    id: int | str
    readings: list[Reading] = []

    class Config:
        from_attributes = True
