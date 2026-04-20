from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    original_path = Column(String)
    processed_path = Column(String)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    is_duplicate = Column(Boolean, default=False)
    is_main_duplicate = Column(Boolean, default=False)
    duplicate_group = Column(String)  # ссылка на основное изображение в группе дубликатов
    is_title_page = Column(Boolean, default=False)
    issue_name = Column(String)  # название выпуска
    issue_number = Column(Integer)  # порядковый номер выпуска
    quality_score = Column(Integer)  # оценка качества изображения
    validation_status = Column(String, default="pending")  # pending, user_validated, leader_validated
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ImageBase(BaseModel):
    filename: str
    original_path: str
    processed_path: str
    is_duplicate: bool = False
    duplicate_group: Optional[int] = None

class ImageCreate(ImageBase):
    pass

class ImageSchema(ImageBase):
    id: int
    task_id: int
    is_validated: bool
    validation_result: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True

class ImageValidation(BaseModel):
    validation_result: Optional[str] = None

class ImageMove(BaseModel):
    new_path: Optional[str] = None
