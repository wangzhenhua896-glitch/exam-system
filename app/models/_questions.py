"""
题目 CRUD + 父子题查询
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def add_question(subject: str, title: str, content: str, original_text: Optional[str], standard_answer: Optional[str], rubric_rules: Optional[str], rubric_points: Optional[str], rubric_script: Optional[str], rubric: str, max_score: float = 10.0, quality_score: Optional[float] = None, question_number: Optional[str] = None, difficulty: Optional[str] = None, exam_name: Optional[str] = None, parent_id: Optional[int] = None, scoring_strategy: Optional[str] = None, content_html: Optional[str] = None, question_type: str = 'essay', workflow_status: Optional[str] = None) -> int:
    """添加题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO questions (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score, question_number, difficulty, exam_name, parent_id, scoring_strategy, content_html, question_type, workflow_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score, question_number, difficulty, exam_name, parent_id, scoring_strategy, content_html, question_type, workflow_status)
    )
    conn.commit()
    question_id = cursor.lastrowid
    conn.close()
    return question_id


def get_questions(subject: Optional[str] = None) -> List[Dict]:
    """获取题目列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject:
        cursor.execute('SELECT * FROM questions WHERE subject = ? ORDER BY id', (subject,))
    else:
        cursor.execute('SELECT * FROM questions ORDER BY id')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_question(question_id: int) -> Optional[Dict]:
    """获取单个题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM questions WHERE id = ?', (question_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_question(question_id: int, subject: str, title: str, content: str, original_text: Optional[str], standard_answer: Optional[str], rubric_rules: Optional[str], rubric_points: Optional[str], rubric_script: Optional[str], rubric: str, max_score: float, quality_score: Optional[float] = None, parent_id: Optional[int] = None, scoring_strategy: Optional[str] = None, content_html: Optional[str] = None, question_type: Optional[str] = None, workflow_status: Optional[str] = None) -> bool:
    """更新题目，自动快照评分脚本版本"""
    from app.models._script_history import save_script_version
    conn = get_db_connection()
    cursor = conn.cursor()

    # 自动快照：检查旧脚本
    cursor.execute('SELECT rubric_script FROM questions WHERE id = ?', (question_id,))
    old_row = cursor.fetchone()
    is_first_script = False
    if old_row:
        old_script = old_row['rubric_script']
        if old_script and old_script.strip() and old_script != rubric_script:
            # 旧脚本非空且有变化 → 保存旧脚本为版本
            cursor.execute(
                'SELECT COALESCE(MAX(version), 0) + 1 FROM rubric_script_history WHERE question_id = ?',
                (question_id,)
            )
            next_ver = cursor.fetchone()[0]
            cursor.execute(
                '''INSERT INTO rubric_script_history
                   (question_id, version, script_text, note) VALUES (?, ?, ?, ?)''',
                (question_id, next_ver, old_script, '自动保存旧版本')
            )
        elif not old_script and rubric_script:
            # 首次设置脚本
            is_first_script = True

    cursor.execute(
        'UPDATE questions SET subject = ?, title = ?, content = ?, original_text = ?, standard_answer = ?, rubric_rules = ?, rubric_points = ?, rubric_script = ?, rubric = ?, max_score = ?, quality_score = ?, parent_id = ?, scoring_strategy = ?, content_html = ?, question_type = ?, workflow_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score, parent_id, scoring_strategy, content_html, question_type or 'essay', workflow_status, question_id)
    )

    # 首次设置脚本 → 记录为版本 1
    if is_first_script:
        cursor.execute(
            'SELECT COALESCE(MAX(version), 0) + 1 FROM rubric_script_history WHERE question_id = ?',
            (question_id,)
        )
        next_ver = cursor.fetchone()[0]
        cursor.execute(
            '''INSERT INTO rubric_script_history
               (question_id, version, script_text, note) VALUES (?, ?, ?, ?)''',
            (question_id, next_ver, rubric_script, '初始版本')
        )

    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def update_workflow_status(question_id: int, workflow_status: str) -> bool:
    """轻量更新 workflow_status，不触发脚本快照"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE questions SET workflow_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (workflow_status, question_id)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def delete_question(question_id: int) -> bool:
    """删除题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 级联删除测试用例和脚本版本历史
    cursor.execute('DELETE FROM test_cases WHERE question_id = ?', (question_id,))
    cursor.execute('DELETE FROM rubric_script_history WHERE question_id = ?', (question_id,))
    cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def get_child_questions(parent_id: int) -> List[Dict]:
    """获取某父题的所有子题"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM questions WHERE parent_id = ? ORDER BY question_number, id', (parent_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_question_with_children(question_id: int) -> Optional[Dict]:
    """获取题目及其子题列表"""
    question = get_question(question_id)
    if not question:
        return None
    children = get_child_questions(question_id)
    question['children'] = children
    return question
