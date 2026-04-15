"""
评分记录 CRUD
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def add_grading_record(question_id: int, student_answer: str, score: float,
                        details: str, model_used: str, confidence: float,
                        grading_flags: str = None, student_id: str = None,
                        student_name: str = None, exam_name: str = None) -> int:
    """添加评分记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO grading_records (question_id, student_answer, score, details, model_used, confidence, grading_flags, student_id, student_name, exam_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (question_id, student_answer, score, details, model_used, confidence, grading_flags, student_id, student_name, exam_name)
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_grading_history(question_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
    """获取评分历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if question_id:
        cursor.execute(
            'SELECT * FROM grading_records WHERE question_id = ? ORDER BY graded_at DESC LIMIT ?',
            (question_id, limit)
        )
    else:
        cursor.execute('SELECT * FROM grading_records ORDER BY graded_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_previous_grade(student_id: str, question_id: int, exclude_record_id: int = None) -> Optional[Dict]:
    """查询同学生同题的最近一次评分记录（排除指定记录ID）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if exclude_record_id:
        cursor.execute(
            'SELECT * FROM grading_records WHERE student_id = ? AND question_id = ? AND id != ? ORDER BY graded_at DESC LIMIT 1',
            (student_id, question_id, exclude_record_id)
        )
    else:
        cursor.execute(
            'SELECT * FROM grading_records WHERE student_id = ? AND question_id = ? ORDER BY graded_at DESC LIMIT 1',
            (student_id, question_id)
        )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
