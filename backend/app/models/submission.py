"""
答题记录模型
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
import enum


class SubmissionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"  # 进行中
    SUBMITTED = "submitted"      # 已提交
    GRADING = "grading"          # 批改中
    COMPLETED = "completed"      # 已完成


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exam_id = Column(Integer, ForeignKey("exams.id"))
    
    # 状态
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.IN_PROGRESS)
    
    # 时间
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))
    
    # 成绩
    total_score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    
    # 关系
    user = relationship("User", back_populates="submissions")
    exam = relationship("Exam", back_populates="submissions")
    answers = relationship("Answer", back_populates="submission", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    
    # 答案内容
    answer_content = Column(Text)           # 学生答案
    
    # 评分
    score = Column(Float, default=0.0)      # 得分
    max_score = Column(Float, default=0.0)  # 满分
    is_correct = Column(String(10))         # 是否正确（客观题）
    feedback = Column(Text)                 # 评语/反馈
    
    # AI 评分相关
    ai_score = Column(Float)                # AI 评分
    ai_feedback = Column(Text)              # AI 评语
    confidence = Column(Float)              # AI 置信度
    needs_manual_review = Column(String(10), default="false")  # 是否需要人工复核
    
    # 关系
    submission = relationship("Submission", back_populates="answers")
    question = relationship("Question", back_populates="answers")
