"""
pytest 共享 fixture — 按科目切换测试数据库

用法示例:
    def test_politics_scoring(test_db):
        # test_db 已切换到对应科目的测试库
        conn = get_db_connection()
        # ... 测试逻辑 ...

    def test_all_subjects(test_db):
        # 配合 conftest.py 中的参数化 fixture，自动遍历所有科目
        conn = get_db_connection()
        # ... 测试逻辑 ...
"""

import os
import pytest
from app.models.db_models import set_db_path, reset_db_path, init_database

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_MAP = {
    'politics': os.path.join(PROJECT_ROOT, 'data', 'test_politics.db'),
    'chinese': os.path.join(PROJECT_ROOT, 'data', 'test_chinese.db'),
    'english': os.path.join(PROJECT_ROOT, 'data', 'test_english.db'),
    'general': os.path.join(PROJECT_ROOT, 'data', 'test_general.db'),
}

ALL_SUBJECTS = ['politics', 'chinese', 'english', 'general']


@pytest.fixture(params=ALL_SUBJECTS)
def test_db(request):
    """按科目切换到测试数据库，测试结束后恢复默认"""
    subject = request.param
    db_path = DB_MAP[subject]
    init_database(db_path)
    set_db_path(db_path)
    yield subject
    reset_db_path()


@pytest.fixture
def politics_db():
    """切换到思政测试库"""
    db_path = DB_MAP['politics']
    init_database(db_path)
    set_db_path(db_path)
    yield db_path
    reset_db_path()


@pytest.fixture
def chinese_db():
    """切换到语文测试库"""
    db_path = DB_MAP['chinese']
    init_database(db_path)
    set_db_path(db_path)
    yield db_path
    reset_db_path()


@pytest.fixture
def english_db():
    """切换到英语测试库"""
    db_path = DB_MAP['english']
    init_database(db_path)
    set_db_path(db_path)
    yield db_path
    reset_db_path()


@pytest.fixture
def general_db():
    """切换到通用测试库"""
    db_path = DB_MAP['general']
    init_database(db_path)
    set_db_path(db_path)
    yield db_path
    reset_db_path()
