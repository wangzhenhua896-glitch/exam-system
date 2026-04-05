"""
答题记录 API
"""

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.submission import Submission, Answer, SubmissionStatus
from app.models.question import Question, QuestionType
from app.models.exam import Exam
from app.models.user import User, UserRole
from app.schemas.submission import SubmissionCreate, SubmissionResponse, AnswerCreate
from app.api.auth import get_current_active_user

router = APIRouter()


@router.get("/my", response_model=List[SubmissionResponse])
def list_my_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取我的答题记录"""
    submissions = db.query(Submission).filter(Submission.user_id == current_user.id).all()
    return submissions


@router.post("/start", response_model=SubmissionResponse)
def start_exam(
    submission_data: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """开始考试"""
    exam = db.query(Exam).filter(Exam.id == submission_data.exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在"
        )
    
    # 检查考试是否已发布
    if not exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试未发布"
        )
    
    # 检查考试时间
    now = datetime.utcnow()
    if exam.start_time and now < exam.start_time:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试尚未开始"
        )
    if exam.end_time and now > exam.end_time:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="考试已结束"
        )
    
    # 检查是否已有进行中的考试
    existing = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.exam_id == exam.id,
        Submission.status == SubmissionStatus.IN_PROGRESS
    ).first()
    
    if existing:
        return existing
    
    # 检查考试次数限制
    if not exam.allow_multiple_attempts:
        previous = db.query(Submission).filter(
            Submission.user_id == current_user.id,
            Submission.exam_id == exam.id,
            Submission.status != SubmissionStatus.IN_PROGRESS
        ).first()
        if previous:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您已完成此考试，不允许重复作答"
            )
    
    # 创建新的答题记录
    new_submission = Submission(
        user_id=current_user.id,
        exam_id=exam.id,
        status=SubmissionStatus.IN_PROGRESS,
        max_score=exam.total_score
    )
    
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)
    
    return new_submission


@router.post("/{submission_id}/answer")
def submit_answer(
    submission_id: int,
    answer_data: AnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """提交答案"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="答题记录不存在"
        )
    
    # 只能提交自己的答案
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此答题记录"
        )
    
    # 检查考试状态
    if submission.status != SubmissionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试已结束"
        )
    
    # 检查题目是否属于该考试
    question = db.query(Question).filter(
        Question.id == answer_data.question_id,
        Question.exam_id == submission.exam_id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在或不属于此考试"
        )
    
    # 检查是否已答过此题
    existing_answer = db.query(Answer).filter(
        Answer.submission_id == submission_id,
        Answer.question_id == answer_data.question_id
    ).first()
    
    # 自动评分（客观题）
    score = 0.0
    is_correct = "false"
    
    if question.type in [QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE]:
        if answer_data.answer_content == question.correct_answer:
            score = question.score
            is_correct = "true"
    elif question.type == QuestionType.MULTIPLE_CHOICE:
        # 多选题：完全正确才给分
        user_answers = set(answer_data.answer_content.split(",")) if answer_data.answer_content else set()
        correct_answers = set(question.correct_answer.split(",")) if question.correct_answer else set()
        if user_answers == correct_answers:
            score = question.score
            is_correct = "true"
    elif question.type == QuestionType.FILL_BLANK:
        # 填空题：完全匹配给分
        if answer_data.answer_content and answer_data.answer_content.strip() == question.correct_answer.strip():
            score = question.score
            is_correct = "true"
    
    if existing_answer:
        # 更新答案
        existing_answer.answer_content = answer_data.answer_content
        existing_answer.score = score
        existing_answer.max_score = question.score
        existing_answer.is_correct = is_correct
    else:
        # 创建新答案
        new_answer = Answer(
            submission_id=submission_id,
            question_id=answer_data.question_id,
            answer_content=answer_data.answer_content,
            score=score,
            max_score=question.score,
            is_correct=is_correct
        )
        db.add(new_answer)
    
    db.commit()
    
    return {"message": "答案已提交", "score": score, "max_score": question.score}


@router.post("/{submission_id}/submit")
def submit_exam(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """提交考试"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="答题记录不存在"
        )
    
    # 只能提交自己的考试
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此答题记录"
        )
    
    # 检查考试状态
    if submission.status != SubmissionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试已结束"
        )
    
    # 计算总分
    answers = db.query(Answer).filter(Answer.submission_id == submission_id).all()
    total_score = sum(answer.score for answer in answers)
    
    # 更新考试状态
    submission.status = SubmissionStatus.SUBMITTED
    submission.submitted_at = datetime.utcnow()
    submission.total_score = total_score
    
    db.commit()
    db.refresh(submission)
    
    return {
        "message": "考试已提交",
        "submission": submission,
        "total_score": total_score,
        "max_score": submission.max_score
    }


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取答题详情"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="答题记录不存在"
        )
    
    # 只能查看自己的答题记录（教师和管理员除外）
    if submission.user_id != current_user.id and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看此答题记录"
        )
    
    return submission
