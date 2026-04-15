"""
验证 conftest.py 的 test_db fixture 是否正确切换数据库
"""
from app.models.db_models import get_db_connection


def test_politics_db_has_questions(politics_db):
    """思政测试库应该有 12 道题"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM questions')
    count = cur.fetchone()[0]
    conn.close()
    assert count == 12, f'Expected 12 questions, got {count}'


def test_english_db_has_questions(english_db):
    """英语测试库应该有 28 道题（7 父题 + 21 子题）"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM questions')
    count = cur.fetchone()[0]
    conn.close()
    assert count == 28, f'Expected 28 questions, got {count}'


def test_english_db_subject_is_english(english_db):
    """英语测试库所有题目都是 english 科目"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT subject FROM questions')
    subjects = {row[0] for row in cur.fetchall()}
    conn.close()
    assert subjects == {'english'}, f'Expected only english, got {subjects}'


def test_chinese_db_has_test_cases(chinese_db):
    """语文测试库应该有测试用例"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM test_cases')
    count = cur.fetchone()[0]
    conn.close()
    assert count > 0, 'Chinese test DB should have test cases'


def test_general_db_has_public_tables(general_db):
    """通用测试库应该有公共表（model_configs, grading_params, users）"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM model_configs')
    mc = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM grading_params')
    gp = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM users')
    u = cur.fetchone()[0]
    conn.close()
    assert mc > 0, 'model_configs should not be empty'
    assert gp > 0, 'grading_params should not be empty'
    assert u > 0, 'users should not be empty'
