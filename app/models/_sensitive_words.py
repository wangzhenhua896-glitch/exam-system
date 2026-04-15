"""
敏感词 CRUD + 扫描
"""
from typing import List, Dict
from app.models._db_core import get_db_connection


def get_sensitive_words(subject: str = None, category: str = None,
                        keyword: str = None, severity: str = None) -> List[Dict]:
    """获取敏感词列表，支持筛选"""
    conn = get_db_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if subject and subject != 'all':
        conditions.append('(subject = ? OR subject = ?)')
        params.extend([subject, 'all'])
    if category:
        conditions.append('category = ?')
        params.append(category)
    if severity:
        conditions.append('severity = ?')
        params.append(severity)
    if keyword:
        conditions.append('word LIKE ?')
        params.append(f'%{keyword}%')
    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    cursor.execute(f'SELECT * FROM sensitive_words {where} ORDER BY created_at DESC', params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def add_sensitive_word(word: str, subject: str = 'all', category: str = 'politics',
                       severity: str = 'high') -> int:
    """添加敏感词"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO sensitive_words (word, subject, category, severity) VALUES (?, ?, ?, ?)',
        (word, subject, category, severity)
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def update_sensitive_word(word_id: int, **kwargs) -> bool:
    """更新敏感词"""
    allowed = {'word', 'subject', 'category', 'severity'}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in fields)
    set_clause += ', updated_at = CURRENT_TIMESTAMP'
    values = list(fields.values()) + [word_id]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE sensitive_words SET {set_clause} WHERE id = ?', values)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_sensitive_word(word_id: int) -> bool:
    """删除敏感词"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sensitive_words WHERE id = ?', (word_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def batch_add_sensitive_words(words: List[Dict]) -> int:
    """批量导入敏感词，返回成功导入数量"""
    conn = get_db_connection()
    cursor = conn.cursor()
    count = 0
    for w in words:
        cursor.execute(
            'INSERT INTO sensitive_words (word, subject, category, severity) VALUES (?, ?, ?, ?)',
            (w['word'], w.get('subject', 'all'), w.get('category', 'politics'), w.get('severity', 'high'))
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def check_sensitive_words(answer: str, subject: str = 'all') -> List[Dict]:
    """扫描答案中的敏感词，返回命中的敏感词列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sensitive_words WHERE subject = ? OR subject = 'all'",
        (subject,)
    )
    words = [dict(r) for r in cursor.fetchall()]
    conn.close()
    hits = []
    for w in words:
        if w['word'] in answer:
            hits.append(w)
    return hits
