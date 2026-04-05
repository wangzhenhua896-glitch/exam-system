"""
答题记录 Schema
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models.submission import SubmissionStatus


class AnswerBase(BaseModel):
    question_id: int
    answer_content: Optional[str] = None


class AnswerCreate(AnswerBase):
    pass


class AnswerResponse(AnswerBase):
    id: int
    submission_id: int
    score: float
    max_score: float
    is_correct: Optional[str] = None
    feedback: Optional[str] = None
    ai_score: Optional[float] = None
    ai_feedback: Optional[str] = None
    confidence: Optional[float] = None
    needs_manual_review: str = "false"

    class Config:
        from_attributes = True


class SubmissionBase(BaseModel):
    exam_id: int


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionResponse(SubmissionBase):
    id: int
    user_id: int
    status: SubmissionStatus
    started_at: datetime
    submitted_at: Optional[datetime] = None
    total_score: float
    max_score: float
    answers: Optional[List[AnswerResponse]] = []

    class Config:
        from_attributes = True
