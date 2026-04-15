"""
评分参数 CRUD
"""
from typing import Optional, Dict
from app.models._db_core import get_db_connection


def get_grading_param(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取单个评分参数"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM grading_params WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def get_all_grading_params() -> Dict[str, str]:
    """获取所有评分参数"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value, description FROM grading_params ORDER BY key')
    params = {row['key']: {'value': row['value'], 'description': row['description']} for row in cursor.fetchall()}
    conn.close()
    return params


def set_grading_param(key: str, value: str, description: str = '') -> None:
    """设置评分参数（有则更新，无则插入）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO grading_params (key, value, description) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = ?, description = ?, updated_at = CURRENT_TIMESTAMP',
        (key, value, description, value, description)
    )
    conn.commit()
    conn.close()
