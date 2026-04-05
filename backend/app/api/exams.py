"""
考试管理 API
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.exam import Exam
from app.models.user import User, UserRole
from app.schemas.exam import ExamCreate, ExamResponse, ExamUpdate
from app.api.auth import get_current_active_user

router = APIRouter()


@router.get("/", response_model=List[ExamResponse])
def list_exams(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取考试列表"""
    # 学生只能看到已发布的考试
    if current_user.role == UserRole.STUDENT:
        exams = db.query(Exam).filter(Exam.is_published == True).offset(skip).limit(limit).all()
    else:
        # 教师和管理员可以看到所有考试
        exams = db.query(Exam).offset(skip).limit(limit).all()
    
    return exams


@router.post("/", response_model=ExamResponse)
def create_exam(
    exam_data: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建考试（仅教师和管理员）"""
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="学生无法创建考试"
        )
    
    new_exam = Exam(
        **exam_data.dict(),
        creator_id=current_user.id
    )
    
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    
    return new_exam


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取考试详情"""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 学生只能查看已发布的考试
    if current_user.role == UserRole.STUDENT and not exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试未发布"
        )
    
    return exam


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: int,
    exam_data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新考试信息"""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 只能修改自己创建的考试（管理员除外）
    if exam.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此考试"
        )
    
    # 更新字段
    for field, value in exam_data.dict(exclude_unset=True).items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    
    return exam


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除考试"""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 只能删除自己创建的考试（管理员除外）
    if exam.creator_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此考试"
        )
    
    db.delete(exam)
    db.commit()
    
    return {"message": "考试已删除"}
