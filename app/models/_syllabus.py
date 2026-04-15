"""
考试大纲/教材 CRUD
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def get_syllabus(subject: str, content_type: str) -> Optional[Dict]:
    """获取某科目的考试大纲或教材内容"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM syllabus WHERE subject = ? AND content_type = ?', (subject, content_type))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_syllabus(subject: Optional[str] = None) -> List[Dict]:
    """获取所有大纲/教材，可按科目筛选"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject:
        cursor.execute('SELECT * FROM syllabus WHERE subject = ? ORDER BY content_type', (subject,))
    else:
        cursor.execute('SELECT * FROM syllabus ORDER BY subject, content_type')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upsert_syllabus(subject: str, content_type: str, title: str, content: str) -> int:
    """新增或更新大纲/教材内容"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM syllabus WHERE subject = ? AND content_type = ?', (subject, content_type))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            'UPDATE syllabus SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE subject = ? AND content_type = ?',
            (title, content, subject, content_type)
        )
        row_id = existing[0]
    else:
        cursor.execute(
            'INSERT INTO syllabus (subject, content_type, title, content) VALUES (?, ?, ?, ?)',
            (subject, content_type, title, content)
        )
        row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def delete_syllabus(subject: str, content_type: str) -> bool:
    """删除大纲/教材内容"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM syllabus WHERE subject = ? AND content_type = ?', (subject, content_type))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0
