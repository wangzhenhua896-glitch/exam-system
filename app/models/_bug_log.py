"""
Bug 日志
"""
from app.models._db_core import get_db_connection


def log_bug(bug_type: str, description: str, details: str = '', question_id: int = None, model_used: str = ''):
    """记录 bug 到 bug_log 表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO bug_log (bug_type, description, details, question_id, model_used) VALUES (?, ?, ?, ?, ?)',
        (bug_type, description, details, question_id, model_used)
    )
    conn.commit()
    conn.close()
