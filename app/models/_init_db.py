"""
数据库表初始化 — CREATE TABLE + ALTER TABLE 兼容旧库 + 数据迁移
"""
from app.models._db_core import get_db_connection, get_db_path


def init_database(db_path=None):
    """初始化数据库表"""
    conn = get_db_connection(db_path)
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
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN original_text TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_rules TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_points TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN rubric_script TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN quality_score REAL DEFAULT NULL')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN question_number TEXT DEFAULT NULL')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT NULL')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN exam_name TEXT DEFAULT NULL')
    except Exception:
        pass
    # 多满分答案：parent_id 支持父子题
    try:
        cursor.execute('ALTER TABLE questions ADD COLUMN parent_id INTEGER DEFAULT NULL REFERENCES questions(id)')
    except Exception:
        pass
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_questions_parent ON questions(parent_id)')
    except Exception:
        pass
    # 单题评分策略覆盖（NULL 使用全局默认）
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN scoring_strategy TEXT DEFAULT NULL")
    except Exception:
        pass
    # 富文本 HTML 内容（前端展示用，评分引擎继续读 content 纯文本）
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN content_html TEXT DEFAULT NULL")
    except Exception:
        pass
    # 题型标识（essay/single_choice/multi_choice/fill_blank/true_false/translation）
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN question_type TEXT DEFAULT 'essay'")
    except Exception:
        pass
    # 工作流状态（独立列，不存 rubric JSON 中，避免保存时被覆盖）
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN workflow_status TEXT DEFAULT NULL")
    except Exception:
        pass

    # grading_records 新字段
    try:
        cursor.execute('ALTER TABLE grading_records ADD COLUMN student_name TEXT DEFAULT NULL')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE grading_records ADD COLUMN exam_name TEXT DEFAULT NULL')
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
            grading_flags TEXT DEFAULT NULL,
            graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')
    # 兼容已有数据库
    try:
        cursor.execute('ALTER TABLE grading_records ADD COLUMN grading_flags TEXT DEFAULT NULL')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE grading_records ADD COLUMN student_id TEXT DEFAULT NULL')
    except Exception:
        pass

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

    # 评分脚本版本历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubric_script_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            script_text TEXT NOT NULL,
            avg_error REAL DEFAULT NULL,
            passed_count INTEGER DEFAULT NULL,
            total_cases INTEGER DEFAULT NULL,
            note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rsh_question_version
        ON rubric_script_history(question_id, version)
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

    # 敏感词表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensitive_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            subject TEXT DEFAULT 'all',
            category TEXT DEFAULT 'politics',
            severity TEXT DEFAULT 'high',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 已有数据迁移：为已有评分脚本回填版本 1（幂等）
    try:
        cursor.execute('''
            INSERT INTO rubric_script_history (question_id, version, script_text, note)
            SELECT id, 1, rubric_script, '迁移：已有脚本（初始版本）'
            FROM questions
            WHERE rubric_script IS NOT NULL AND rubric_script != ''
            AND id NOT IN (SELECT question_id FROM rubric_script_history)
        ''')
    except Exception:
        pass

    # Bug 日志表（内部记录评分异常）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bug_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bug_type TEXT NOT NULL,
            description TEXT NOT NULL,
            details TEXT DEFAULT '',
            question_id INTEGER,
            model_used TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            role TEXT DEFAULT 'teacher',
            subject TEXT DEFAULT NULL,
            teacher_name TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 兼容旧库：如果 teacher_name 列不存在则添加
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN teacher_name TEXT DEFAULT NULL')
    except Exception:
        pass
    # 预置默认用户（幂等）
    default_users = [
        ('admin', '管理员', 'admin', None),
        ('politics', '思政老师', 'teacher', 'politics'),
        ('chinese', '语文老师', 'teacher', 'chinese'),
        ('english', '英语老师', 'teacher', 'english'),
        ('math', '数学老师', 'teacher', 'math'),
        ('history', '历史老师', 'teacher', 'history'),
        ('geography', '地理老师', 'teacher', 'geography'),
        ('physics', '物理老师', 'teacher', 'physics'),
        ('chemistry', '化学老师', 'teacher', 'chemistry'),
        ('biology', '生物老师', 'teacher', 'biology'),
    ]
    for u in default_users:
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO users (username, display_name, role, subject) VALUES (?, ?, ?, ?)',
                u
            )
        except Exception:
            pass

    # 满分答案表（多满分答案支持）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL DEFAULT 'question',
            scope_id TEXT DEFAULT '',
            score_ratio REAL DEFAULT 1.0,
            answer_text TEXT NOT NULL,
            label TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_qa_question ON question_answers(question_id, scope_type)
    ''')

    # 评分参数配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grading_params (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 初始化默认阈值（幂等）
    default_params = [
        ('match_pass_threshold', '0.80', '学生答案与满分答案的匹配度高于此值，直接判定得分，不再调用AI'),
        ('match_review_threshold', '0.65', '匹配度在此区间，交给AI复核后给分'),
        ('full_check_threshold', '0.72', '整题评分后的校验阈值，偏离此值触发复查'),
        ('scoring_strategy', 'avg', '全局评分策略：max / min / avg / median'),
    ]
    for p in default_params:
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO grading_params (key, value, description) VALUES (?, ?, ?)',
                p
            )
        except Exception:
            pass

    # 迁移已有 standard_answer 到 question_answers（幂等）
    try:
        cursor.execute('''
            INSERT INTO question_answers (question_id, scope_type, scope_id, score_ratio, answer_text, label, source)
            SELECT id, 'question', '', 1.0, standard_answer, '标准答案', 'migrated'
            FROM questions
            WHERE standard_answer IS NOT NULL AND standard_answer != ''
            AND id NOT IN (SELECT question_id FROM question_answers WHERE scope_type = 'question' AND label = '标准答案')
        ''')
    except Exception:
        pass

    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {db_path or get_db_path()}")
