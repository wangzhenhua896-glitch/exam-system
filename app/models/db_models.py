"""
SQLite数据库模型
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'exam_system.db')


def get_db_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 题目表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            original_text TEXT,
            standard_answer TEXT,
            rubric_rules TEXT,
            rubric_points TEXT,
            rubric_script TEXT,
            rubric TEXT NOT NULL,
            max_score REAL DEFAULT 10.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 尝试为已有表添加新列（兼容已有数据库）
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN standard_answer TEXT')
    except Exception:
        # 列已存在，忽略
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN original_text TEXT')
    except Exception:
        # 列已存在，忽略
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_rules TEXT')
    except Exception:
        # 列已存在，忽略
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_points TEXT')
    except Exception:
        # 列已存在，忽略
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_script TEXT')
    except Exception:
        # 列已存在，忽略
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN quality_score REAL DEFAULT NULL')
    except Exception:
        pass

    # 评分记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grading_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            student_answer TEXT NOT NULL,
            score REAL,
            details TEXT,
            model_used TEXT,
            confidence REAL,
            graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')

    # 评分规则表（题库）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            points TEXT NOT NULL,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')

    # 批量评分任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT,
            total_count INTEGER DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            results TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # 考试大纲/教材内容表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS syllabus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject, content_type)
        )
    ''')

    # 测试用例表（评分脚本验证）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            answer_text TEXT NOT NULL,
            expected_score REAL NOT NULL,
            description TEXT DEFAULT '',
            case_type TEXT DEFAULT 'simulated',
            last_actual_score REAL DEFAULT NULL,
            last_error REAL DEFAULT NULL,
            last_run_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 模型配置表（管理员通过 Web UI 配置，覆盖 .env 默认值）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_configs (
            provider TEXT PRIMARY KEY,
            api_key TEXT DEFAULT '',
            base_url TEXT DEFAULT '',
            model TEXT DEFAULT '',
            enabled INTEGER DEFAULT 0,
            extra_config TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {DB_PATH}")


# 考试大纲/教材操作
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


# 测试用例统计概览
def get_all_test_cases_overview() -> List[Dict]:
    """获取所有题目的测试用例统计概览"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            q.id AS question_id,
            q.title,
            q.subject,
            q.max_score,
            q.rubric_script IS NOT NULL AND q.rubric_script != '' AS has_rubric_script,
            COUNT(tc.id) AS total_cases,
            COALESCE(SUM(CASE WHEN tc.case_type = 'simulated' THEN 1 ELSE 0 END), 0) AS simulated_count,
            COALESCE(SUM(CASE WHEN tc.case_type = 'real' THEN 1 ELSE 0 END), 0) AS real_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NOT NULL AND tc.last_error <= 1.0 THEN 1 ELSE 0 END), 0) AS passed_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NOT NULL AND tc.last_error > 1.0 THEN 1 ELSE 0 END), 0) AS failed_count,
            COALESCE(SUM(CASE WHEN tc.last_run_at IS NULL THEN 1 ELSE 0 END), 0) AS never_run_count,
            ROUND(AVG(CASE WHEN tc.last_run_at IS NOT NULL THEN tc.last_error END), 2) AS avg_error,
            MAX(tc.last_run_at) AS last_run_at
        FROM questions q
        LEFT JOIN test_cases tc ON q.id = tc.question_id
        GROUP BY q.id
        ORDER BY q.id
    ''')
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


# 测试用例操作
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


# 题目操作
def add_question(subject: str, title: str, content: str, original_text: Optional[str], standard_answer: Optional[str], rubric_rules: Optional[str], rubric_points: Optional[str], rubric_script: Optional[str], rubric: str, max_score: float = 10.0, quality_score: Optional[float] = None) -> int:
    """添加题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO questions (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score)
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


def update_question(question_id: int, subject: str, title: str, content: str, original_text: Optional[str], standard_answer: Optional[str], rubric_rules: Optional[str], rubric_points: Optional[str], rubric_script: Optional[str], rubric: str, max_score: float, quality_score: Optional[float] = None) -> bool:
    """更新题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE questions SET subject = ?, title = ?, content = ?, original_text = ?, standard_answer = ?, rubric_rules = ?, rubric_points = ?, rubric_script = ?, rubric = ?, max_score = ?, quality_score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (subject, title, content, original_text, standard_answer, rubric_rules, rubric_points, rubric_script, rubric, max_score, quality_score, question_id)
    )
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


def delete_question(question_id: int) -> bool:
    """删除题目"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 级联删除测试用例
    cursor.execute('DELETE FROM test_cases WHERE question_id = ?', (question_id,))
    cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


# 评分记录操作
def add_grading_record(question_id: int, student_answer: str, score: float,
                        details: str, model_used: str, confidence: float) -> int:
    """添加评分记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO grading_records (question_id, student_answer, score, details, model_used, confidence) VALUES (?, ?, ?, ?, ?, ?)',
        (question_id, student_answer, score, details, model_used, confidence)
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_grading_history(question_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
    """获取评分历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if question_id:
        cursor.execute(
            'SELECT * FROM grading_records WHERE question_id = ? ORDER BY graded_at DESC LIMIT ?',
            (question_id, limit)
        )
    else:
        cursor.execute('SELECT * FROM grading_records ORDER BY graded_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# 批量任务操作
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


# 模型配置操作
def get_model_configs() -> List[Dict]:
    """获取所有模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM model_configs ORDER BY provider')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_model_config(provider: str) -> Optional[Dict]:
    """获取单个 provider 的模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM model_configs WHERE provider = ?', (provider,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_model_config(provider: str, api_key: str, base_url: str, model: str, enabled: bool, extra_config: str = '{}') -> int:
    """新增或更新模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT provider FROM model_configs WHERE provider = ?', (provider,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            'UPDATE model_configs SET api_key = ?, base_url = ?, model = ?, enabled = ?, extra_config = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = ?',
            (api_key, base_url, model, 1 if enabled else 0, extra_config, provider)
        )
    else:
        cursor.execute(
            'INSERT INTO model_configs (provider, api_key, base_url, model, enabled, extra_config) VALUES (?, ?, ?, ?, ?, ?)',
            (provider, api_key, base_url, model, 1 if enabled else 0, extra_config)
        )
    conn.commit()
    conn.close()
    return 1


def delete_model_config(provider: str) -> bool:
    """删除模型配置（回退到 .env 默认值）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM model_configs WHERE provider = ?', (provider,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


# 初始化数据库
init_database()
