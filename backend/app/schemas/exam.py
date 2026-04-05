"""
考试 Schema
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ExamBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: int = 60
    total_score: float = 100.0
    pass_score: float = 60.0
    is_published: bool = False
    allow_multiple_attempts: bool = False
    max_attempts: int = 1
    shuffle_questions: bool = False
    shuffle_options: bool = False


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    total_score: Optional[float] = None
    pass_score: Optional[float] = None
    is_published: Optional[bool] = None
    allow_multiple_attempts: Optional[bool] = None
    max_attempts: Optional[int] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None


class ExamResponse(ExamBase):
    id: int
    creator_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
