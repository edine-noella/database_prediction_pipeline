from typing import Literal, Optional, Union
from .sqlite_db import SQLiteDatabase
from .mongodb_db import MongoDB
from .base import Database

# Type hint for database types
DatabaseType = Literal['sqlite', 'mongodb']

# Global database instances
_sqlite_db: Optional[SQLiteDatabase] = None
_mongodb: Optional[MongoDB] = None

def init_db():
    """Initialize database connections"""
    global _sqlite_db, _mongodb
    if _sqlite_db is None:
        _sqlite_db = SQLiteDatabase()
    if _mongodb is None:
        _mongodb = MongoDB()
    return _sqlite_db, _mongodb

def get_database(db_type: DatabaseType = 'sqlite', **kwargs) -> Database:
    """
    Factory function to get the appropriate database instance.
    
    Args:
        db_type: Either 'sqlite' or 'mongodb'
        **kwargs: Additional arguments for the database connection
        
    Returns:
        An instance of the requested database adapter
    """
    global _sqlite_db, _mongodb
    
    if db_type == 'sqlite':
        if _sqlite_db is None:
            _sqlite_db = SQLiteDatabase(**kwargs)
        return _sqlite_db
    elif db_type == 'mongodb':
        db = MongoDB(**kwargs)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    return db

# Initialize with default database (SQLite)
db = get_database('sqlite')
