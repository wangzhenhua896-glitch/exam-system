"""
测试用例 CRUD + 概览统计
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def get_all_test_cases_overview(subject: Optional[str] = None) -> List[Dict]:
    """获取所有题目的测试用例统计概览，支持科目筛选"""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT
            q.id AS question_id,
            q.title,
            q.subject,
            q.max_score,
            q.rubric_script IS NOT NULL AND q.rubric_script != '' AS has_rubric_script,
            COUNT(tc.id) AS total_cases,
            COALESCE(SUM(CASE WHEN tc.case_type = 'ai_generated' THEN 1 ELSE 0 END), 0) AS ai_count,
            COALESCE(SUM(CASE WHEN tc.case_type = 'simulated' THEN 1 ELSE 0 END), 0) AS simulated_count,
            COALESCE(SUM(CASE WHEN tc.case_type = 'real' THEN 1 ELSE 0 END), 0) AS real_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NOT NULL AND tc.last_error <= 1.0 THEN 1 ELSE 0 END), 0) AS passed_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NOT NULL AND tc.last_error > 1.0 THEN 1 ELSE 0 END), 0) AS failed_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NULL THEN 1 ELSE 0 END), 0) AS never_run_count,
            ROUND(AVG(CASE WHEN tc.last_run_at IS NOT NULL THEN tc.last_error END), 2) AS avg_error,
            MAX(tc.last_run_at) AS last_run_at
        FROM questions q
        LEFT JOIN test_cases tc ON q.id = tc.question_id
    '''
    if subject:
        sql += ' WHERE q.subject = ? '
        cursor.execute(sql + 'GROUP BY q.id ORDER BY q.id', (subject,))
    else:
        cursor.execute(sql + 'GROUP BY q.id ORDER BY q.id')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_test_cases_with_question(subject: Optional[str] = None) -> List[Dict]:
    """获取所有测试用例（含题目信息），支持科目筛选"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject:
        cursor.execute('''
            SELECT tc.*, q.title AS question_title, q.subject, q.max_score
            FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ?
            ORDER BY tc.question_id, tc.created_at
        ''', (subject,))
    else:
        cursor.execute('''
            SELECT tc.*, q.title AS question_title, q.subject, q.max_score
            FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            ORDER BY tc.question_id, tc.created_at
        ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_test_case(question_id: int, answer_text: str, expected_score: float, description: str = '', case_type: str = 'simulated') -> int:
    """添加测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO test_cases (question_id, answer_text, expected_score, description, case_type) VALUES (?, ?, ?, ?, ?)',
        (question_id, answer_text, expected_score, description, case_type)
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_test_cases(question_id: int) -> List[Dict]:
    """获取某题目的所有测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM test_cases WHERE question_id = ? ORDER BY created_at', (question_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_test_case(test_case_id: int) -> Optional[Dict]:
    """获取单个测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM test_cases WHERE id = ?', (test_case_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_test_case(test_case_id: int, answer_text: str, expected_score: float, description: str, case_type: str) -> bool:
    """更新测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE test_cases SET answer_text = ?, expected_score = ?, description = ?, case_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (answer_text, expected_score, description, case_type, test_case_id)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def delete_test_case(test_case_id: int) -> bool:
    """删除测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM test_cases WHERE id = ?', (test_case_id,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def update_test_case_result(test_case_id: int, actual_score: float, error: float) -> bool:
    """更新测试用例的验证结果"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE test_cases SET last_actual_score = ?, last_error = ?, last_run_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (actual_score, error, test_case_id)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def delete_test_cases_by_question(question_id: int):
    """删除某题目的所有测试用例"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM test_cases WHERE question_id = ?', (question_id,))
    conn.commit()
    conn.close()
