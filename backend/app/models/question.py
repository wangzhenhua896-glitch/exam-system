"""
题目模型
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text, Enum, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
import enum


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"      # 单选题
    MULTIPLE_CHOICE = "multiple_choice"  # 多选题
    TRUE_FALSE = "true_false"            # 判断题
    FILL_BLANK = "fill_blank"            # 填空题
    SHORT_ANSWER = "short_answer"        # 简答题


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    
    # 题目内容
    type = Column(Enum(QuestionType), nullable=False)
    content = Column(Text, nullable=False)  # 题目内容
    options = Column(JSON, default=list)    # 选项（选择题）
    correct_answer = Column(Text)           # 正确答案
    score = Column(Float, default=10.0)     # 分值
    
    # 顺序
    order_num = Column(Integer, default=0)
    
    # AI 评分设置（简答题）
    scoring_criteria = Column(Text)         # 评分标准
    keywords = Column(JSON, default=list)   # 关键词
    
    # 关系
    exam = relationship("Exam", back_populates="questions")
    answers = relationship("Answer", back_populates="question")
