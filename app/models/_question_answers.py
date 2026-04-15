"""
满分答案 CRUD
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def get_question_answers(question_id: int, scope_type: Optional[str] = None) -> List[Dict]:
    """获取某题的满分答案列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if scope_type:
        cursor.execute(
            'SELECT * FROM question_answers WHERE question_id = ? AND scope_type = ? ORDER BY scope_id, sort_order, id',
            (question_id, scope_type)
        )
    else:
        cursor.execute(
            'SELECT * FROM question_answers WHERE question_id = ? ORDER BY scope_type, scope_id, sort_order, id',
            (question_id,)
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def add_question_answer(question_id: int, scope_type: str = 'question', scope_id: str = '',
                        score_ratio: float = 1.0, answer_text: str = '', label: str = '',
                        source: str = 'manual', sort_order: int = 0) -> int:
    """添加一个满分答案，返回新 ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO question_answers
           (question_id, scope_type, scope_id, score_ratio, answer_text, label, source, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (question_id, scope_type, scope_id, score_ratio, answer_text, label, source, sort_order)
    )
    answer_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return answer_id


def update_question_answer(answer_id: int, **kwargs) -> bool:
    """更新满分答案"""
    allowed = {'scope_type', 'scope_id', 'score_ratio', 'answer_text', 'label', 'source', 'sort_order'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in fields)
    values = list(fields.values()) + [answer_id]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE question_answers SET {set_clause} WHERE id = ?', values)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_question_answer(answer_id: int) -> bool:
    """删除一个满分答案"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM question_answers WHERE id = ?', (answer_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0
