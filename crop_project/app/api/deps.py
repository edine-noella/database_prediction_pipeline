from typing import Generator
from fastapi import Depends, HTTPException, status
from app.database import get_database, Database

def get_db() -> Generator[Database, None, None]:
    """Dependency for SQLite database"""
    db = get_database('sqlite')
    try:
        yield db
    finally:
        # No need to close as we're reusing connections
        pass

def get_mongodb() -> Generator[Database, None, None]:
    """Dependency for MongoDB"""
    db = get_database('mongodb')
    try:
        yield db
    finally:
        # No need to close as we're reusing connections
        pass
