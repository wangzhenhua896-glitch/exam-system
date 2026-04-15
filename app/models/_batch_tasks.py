"""
批量评分任务 CRUD
"""
from typing import Optional, Dict
from app.models._db_core import get_db_connection


def create_batch_task(task_name: str, total_count: int) -> int:
    """创建批量任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO batch_tasks (task_name, total_count) VALUES (?, ?)',
        (task_name, total_count)
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def update_batch_task(task_id: int, completed_count: int, results: str = None,
                      status: str = 'running'):
    """更新批量任务进度"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'completed':
        cursor.execute(
            'UPDATE batch_tasks SET completed_count = ?, results = ?, status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (completed_count, results, status, task_id)
        )
    else:
        cursor.execute(
            'UPDATE batch_tasks SET completed_count = ?, results = ?, status = ? WHERE id = ?',
            (completed_count, results, status, task_id)
        )
    conn.commit()
    conn.close()


def get_batch_task(task_id: int) -> Optional[Dict]:
    """获取批量任务状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM batch_tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
