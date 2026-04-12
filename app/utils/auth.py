from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Generator

from app.database import SessionLocal

def get_db() -> Generator[Session, None, None]:
    """
    Зависимость для получения сессии базы данных
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()