"""
题目 Schema
"""

from pydantic import BaseModel
from typing import Optional, List, Any

from app.models.question import QuestionType


class QuestionBase(BaseModel):
    type: QuestionType
    content: str
    options: Optional[List[str]] = []
    correct_answer: Optional[str] = None
    score: float = 10.0
    order_num: int = 0
    scoring_criteria: Optional[str] = None
    keywords: Optional[List[str]] = []


class QuestionCreate(QuestionBase):
    exam_id: int


class QuestionUpdate(BaseModel):
    type: Optional[QuestionType] = None
    content: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    score: Optional[float] = None
    order_num: Optional[int] = None
    scoring_criteria: Optional[str] = None
    keywords: Optional[List[str]] = None


class QuestionResponse(QuestionBase):
    id: int
    exam_id: int

    class Config:
        from_attributes = True
