from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, in_progress, completed, validated, stopped, paused
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validator_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    input_path = Column(String)
    output_path = Column(String)
    output_path_stage2 = Column(String)
    stage = Column(Integer, default=1)  # 1: duplicates, 2: grouping
    progress = Column(Integer, default=0)
    total_images = Column(Integer, default=0)
    
    # Параметры первого этапа (поиск дубликатов)
    #first_image = Column(Integer)
    #last_image = Column(Integer)
    feature_extractor_stage1 = Column(String)
    matcher_stage1 = Column(String)
    quality_algorithm = Column(String)
    match_threshold_stage1 = Column(Float)
    duplicate_threshold_stage1 = Column(Float)
    
    # Параметры второго этапа (кластеризация по выпускам)
    feature_extractor_stage2 = Column(String)
    matcher_stage2 = Column(String)
    duplicate_threshold_stage2 = Column(Float)
    logos_path = Column(String)
    
    # Параметры валидации
    validate_stage1 = Column(Boolean, default=False)
    validate_stage2 = Column(Boolean, default=False)

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    input_path: str
    output_path: str
    output_path_stage2: Optional[str] = None
    status: str = 'pending'
    stage: int = 1
    owner_id: int

    # Параметры первого этапа
    first_image: Optional[int] = None
    last_image: Optional[int] = None
    feature_extractor_stage1: Optional[str] = 'SIFT'
    matcher_stage1: Optional[str] = 'FLANN'
    quality_algorithm: Optional[str] = 'BRISQUE'
    match_threshold_stage1: Optional[float] = 0.75
    duplicate_threshold_stage1: Optional[float] = 0.9

    # Параметры второго этапа
    feature_extractor_stage2: Optional[str] = 'SIFT'
    matcher_stage2: Optional[str] = 'FLANN'
    duplicate_threshold_stage2: Optional[float] = 0.8
    logos_path: Optional[str] = ''

    # Параметры валидации
    validate_stage1: bool = False
    validate_stage2: bool = False

class TaskCreate(TaskBase):
    pass

class TaskSchema(TaskBase):
    id: int
    assigned_to: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    validator_id: Optional[int] = None

    class Config:
        orm_mode = True
