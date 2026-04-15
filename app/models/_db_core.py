"""
数据库连接核心 — DB_PATH、get_db_connection、set/reset_db_path
所有子模块从此导入 get_db_connection，不直接操作 sqlite3。
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'exam_system.db')
_override_path = None


def get_db_connection(db_path=None):
    """获取数据库连接"""
    path = db_path or _override_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def set_db_path(path):
    """设置全局数据库路径覆盖，测试用"""
    global _override_path
    _override_path = path


def reset_db_path():
    """恢复默认数据库路径"""
    global _override_path
    _override_path = None


def get_db_path():
    """获取当前生效的数据库路径"""
    return _override_path or DB_PATH
