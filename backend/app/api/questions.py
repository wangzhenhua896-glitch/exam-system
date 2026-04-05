"""
题目管理 API
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.question import Question
from app.models.exam import Exam
from app.models.user import User, UserRole
from app.schemas.question import QuestionCreate, QuestionResponse, QuestionUpdate
from app.api.auth import get_current_active_user

router = APIRouter()


@router.get("/exam/{exam_id}", response_model=List[QuestionResponse])
def list_questions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取考试的所有题目"""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 学生只能查看已发布考试的题目
    if current_user.role == UserRole.STUDENT and not exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试未发布"
        )
    
    questions = db.query(Question).filter(Question.exam_id == exam_id).order_by(Question.order_num).all()
    return questions


@router.post("/", response_model=QuestionResponse)
def create_question(
    question_data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建题目（仅教师和管理员）"""
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="学生无法创建题目"
        )
    
    # 检查考试是否存在
    exam = db.query(Exam).filter(Exam.id == question_data.exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 只能给自己创建的考试添加题目（管理员除外）
    if exam.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此考试添加题目"
        )
    
    new_question = Question(**question_data.dict())
    
    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    
    return new_question


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取题目详情"""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在"
        )
    
    # 学生只能查看已发布考试的题目
    if current_user.role == UserRole.STUDENT and not question.exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试未发布"
        )
    
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新题目"""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在"
        )
    
    # 只能修改自己创建的考试的题目（管理员除外）
    if question.exam.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此题目"
        )
    
    # 更新字段
    for field, value in question_data.dict(exclude_unset=True).items():
        setattr(question, field, value)
    
    db.commit()
    db.refresh(question)
    
    return question


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除题目"""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在"
        )
    
    # 只能删除自己创建的考试的题目（管理员除外）
    if question.exam.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此题目"
        )
    
    db.delete(question)
    db.commit()
    
    return {"message": "题目已删除"}
