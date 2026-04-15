"""
SQLite 数据库模型 — 聚合入口

所有函数从子模块 re-export，保持 `from app.models.db_models import xxx` 不受影响。
"""
# ─── 连接管理 ───
from app.models._db_core import DB_PATH, get_db_connection, set_db_path, reset_db_path  # noqa: F401

# ─── 数据库初始化 ───
from app.models._init_db import init_database  # noqa: F401

# ─── 题目 CRUD + 父子题 ───
from app.models._questions import (  # noqa: F401
    add_question, get_questions, get_question,
    update_question, update_workflow_status, delete_question,
    get_child_questions, get_question_with_children,
)

# ─── 评分记录 ───
from app.models._grading_records import (  # noqa: F401
    add_grading_record, get_grading_history, get_previous_grade,
)

# ─── 测试用例 ───
from app.models._test_cases import (  # noqa: F401
    get_all_test_cases_overview, get_all_test_cases_with_question,
    add_test_case, get_test_cases, get_test_case,
    update_test_case, delete_test_case, update_test_case_result,
    delete_test_cases_by_question,
)

# ─── 评分脚本版本历史 ───
from app.models._script_history import (  # noqa: F401
    save_script_version, get_script_history, get_script_version,
    delete_script_history, update_script_version_result,
)

# ─── 模型配置 ───
from app.models._model_configs import (  # noqa: F401
    get_model_configs, get_model_config, upsert_model_config,
    delete_model_config, get_effective_config, get_all_effective_configs,
)

# ─── 敏感词 ───
from app.models._sensitive_words import (  # noqa: F401
    get_sensitive_words, add_sensitive_word, update_sensitive_word,
    delete_sensitive_word, batch_add_sensitive_words, check_sensitive_words,
)

# ─── 用户 ───
from app.models._users import (  # noqa: F401
    get_users, get_user, add_user, update_user, delete_user,
)

# ─── 满分答案 ───
from app.models._question_answers import (  # noqa: F401
    get_question_answers, add_question_answer,
    update_question_answer, delete_question_answer,
)

# ─── 评分参数 ───
from app.models._grading_params import (  # noqa: F401
    get_grading_param, get_all_grading_params, set_grading_param,
)

# ─── 批量任务 ───
from app.models._batch_tasks import (  # noqa: F401
    create_batch_task, update_batch_task, get_batch_task,
)

# ─── 考试大纲 ───
from app.models._syllabus import (  # noqa: F401
    get_syllabus, get_all_syllabus, upsert_syllabus, delete_syllabus,
)

# ─── Bug 日志 ───
from app.models._bug_log import log_bug  # noqa: F401

# 初始化数据库
init_database()
