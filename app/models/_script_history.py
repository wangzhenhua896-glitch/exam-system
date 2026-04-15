"""
评分脚本版本历史
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def save_script_version(question_id: int, script_text: str, note: str = '',
                         avg_error: float = None, passed_count: int = None,
                         total_cases: int = None) -> int:
    """保存一个脚本版本，version 自动递增"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COALESCE(MAX(version), 0) + 1 FROM rubric_script_history WHERE question_id = ?',
        (question_id,)
    )
    next_ver = cursor.fetchone()[0]
    cursor.execute(
        '''INSERT INTO rubric_script_history
           (question_id, version, script_text, note, avg_error, passed_count, total_cases)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (question_id, next_ver, script_text, note, avg_error, passed_count, total_cases)
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_script_history(question_id: int) -> List[Dict]:
    """获取某题目的所有脚本版本，version DESC"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM rubric_script_history WHERE question_id = ? ORDER BY version DESC',
        (question_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_script_version(question_id: int, version: int) -> Optional[Dict]:
    """获取单个脚本版本"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM rubric_script_history WHERE question_id = ? AND version = ?',
        (question_id, version)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_script_history(question_id: int):
    """删除某题目的所有脚本版本"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rubric_script_history WHERE question_id = ?', (question_id,))
    conn.commit()
    conn.close()


def update_script_version_result(question_id: int, version: int,
                                  avg_error: float, passed_count: int,
                                  total_cases: int) -> bool:
    """更新某版本的验证结果"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE rubric_script_history
           SET avg_error = ?, passed_count = ?, total_cases = ?
           WHERE question_id = ? AND version = ?''',
        (avg_error, passed_count, total_cases, question_id, version)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0
