from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class Database(ABC):
    """Abstract base class for database operations"""
    
    @abstractmethod
    def get_crops(self) -> List[Dict[str, Any]]:
        """Get all crops"""
        pass
    
    @abstractmethod
    def get_soil_types(self) -> List[Dict[str, Any]]:
        """Get all soil types"""
        pass
    
    @abstractmethod
    def get_growth_stages(self) -> List[Dict[str, Any]]:
        """Get all growth stages"""
        pass
    
    @abstractmethod
    def get_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get readings with optional limit"""
        pass
    
    @abstractmethod
    def add_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new reading"""
        pass
    
    @abstractmethod
    def update_reading(self, reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing reading with new data
        
        Args:
            reading_data: Dictionary containing reading data including 'id' or '_id'
            
        Returns:
            Dict: The updated reading document
        """
        pass
    
    @abstractmethod
    def close(self):
        """Close database connection"""
        pass
