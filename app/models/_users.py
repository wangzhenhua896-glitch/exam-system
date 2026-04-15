"""
用户 CRUD
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def get_users() -> List[Dict]:
    """获取所有用户列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY id')
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users


def get_user(username: str) -> Optional[Dict]:
    """按用户名查询用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_user(username: str, display_name: str = '', role: str = 'teacher',
             subject: str = None) -> int:
    """新增用户，返回新用户ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (username, display_name, role, subject) VALUES (?, ?, ?, ?)',
        (username, display_name, role, subject)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def update_user(user_id: int, **kwargs) -> bool:
    """更新用户信息"""
    allowed = {'username', 'display_name', 'role', 'subject', 'teacher_name', 'is_active'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in fields)
    values = list(fields.values()) + [user_id]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_user(user_id: int) -> bool:
    """删除用户"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0
