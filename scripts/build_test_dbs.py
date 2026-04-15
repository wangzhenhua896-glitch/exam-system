"""
从生产库 (data/exam_system.db) 按科目拆分出 4 个精简测试数据库。

精简策略（优先级从高到低）：
1. 有 rubric + 有满分答案 + 有测试用例  →  必选
2. 有 rubric + 有满分答案（无测试用例） →  补齐到至少 3 道
3. 全部题目 →  仍不足 3 道则全保留

每个测试库还包含：
- 关联的子题、question_answers、test_cases、rubric_script_history、grading_records
- 公共表完整复制：model_configs、grading_params、users、sensitive_words
- 空表建表：batch_tasks、bug_log、syllabus、rubrics
"""

import sqlite3
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DB = os.path.join(PROJECT_ROOT, 'data', 'exam_system.db')
SUBJECTS = ['politics', 'chinese', 'english', 'general']


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(conn, table):
    """获取表的列名列表"""
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info({table})')
    return [row[1] for row in cursor.fetchall()]


def copy_table(src, dst, table, where=None, params=None):
    """按条件复制表数据，保留表结构"""
    src_cur = src.cursor()
    dst_cur = dst.cursor()

    # 建表（如果不存在）
    src_cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    row = src_cur.fetchone()
    if not row or not row[0]:
        return 0
    # 检查目标库是否已有该表
    dst_cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    if not dst_cur.fetchone():
        dst_cur.execute(row[0])

    # 复制数据
    query = f'SELECT * FROM {table}'
    if where:
        query += f' WHERE {where}'
    src_cur.execute(query, params or [])
    rows = src_cur.fetchall()
    if not rows:
        return 0

    columns = [desc[0] for desc in src_cur.description]
    placeholders = ', '.join(['?'] * len(columns))
    col_str = ', '.join(columns)
    for r in rows:
        dst_cur.execute(
            f'INSERT INTO {table} ({col_str}) VALUES ({placeholders})',
            [r[c] for c in columns]
        )
    return len(rows)


def create_empty_tables(dst, src):
    """在目标库中创建源库中存在但目标库还没有的表（不复制数据）"""
    src_cur = src.cursor()
    dst_cur = dst.cursor()
    src_cur.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    for name, create_sql in src_cur.fetchall():
        dst_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        if not dst_cur.fetchone() and create_sql:
            dst_cur.execute(create_sql)


def build_subject_db(subject, src, project_root):
    """为单个科目构建测试数据库"""
    dst_path = os.path.join(project_root, 'data', f'test_{subject}.db')
    # 删除旧的
    if os.path.exists(dst_path):
        os.remove(dst_path)

    dst = get_conn(dst_path)
    dst_cur = dst.cursor()
    src_cur = src.cursor()

    # === 1. 筛选题目 ===
    # 第一轮：有 rubric + 有满分答案 + 有测试用例
    src_cur.execute('''
        SELECT DISTINCT q.id FROM questions q
        WHERE q.subject = ?
        AND q.rubric IS NOT NULL AND q.rubric != ''
        AND q.standard_answer IS NOT NULL AND q.standard_answer != ''
        AND EXISTS (SELECT 1 FROM test_cases tc WHERE tc.question_id = q.id)
    ''', (subject,))
    full_ids = {row[0] for row in src_cur.fetchall()}

    # 第二轮：有 rubric + 有满分答案（不考虑测试用例）
    src_cur.execute('''
        SELECT id FROM questions
        WHERE subject = ?
        AND rubric IS NOT NULL AND rubric != ''
        AND standard_answer IS NOT NULL AND standard_answer != ''
    ''', (subject,))
    partial_ids = {row[0] for row in src_cur.fetchall()}

    # 第三轮：该科目全部题目
    src_cur.execute('SELECT id FROM questions WHERE subject = ?', (subject,))
    all_ids = {row[0] for row in src_cur.fetchall()}

    # 按优先级选择题目
    if len(full_ids) >= 3:
        selected_ids = full_ids
        tier = '完整配置'
    elif len(partial_ids) >= 3:
        selected_ids = partial_ids
        tier = '有rubric+满分答案'
    else:
        selected_ids = all_ids
        tier = '全部题目'

    # 补充子题：把所有选中题目的子题也拉进来
    if selected_ids:
        placeholders = ', '.join(['?'] * len(selected_ids))
        src_cur.execute(
            f'SELECT id FROM questions WHERE parent_id IN ({placeholders})',
            list(selected_ids)
        )
        child_ids = {row[0] for row in src_cur.fetchall()}
        selected_ids = selected_ids | child_ids

    # 也把选中题目的父题拉进来（如果某些子题被选中但父题没被选中）
    if selected_ids:
        placeholders = ', '.join(['?'] * len(selected_ids))
        src_cur.execute(
            f'SELECT DISTINCT parent_id FROM questions WHERE id IN ({placeholders}) AND parent_id IS NOT NULL',
            list(selected_ids)
        )
        parent_ids = {row[0] for row in src_cur.fetchall() if row[0] not in selected_ids}
        selected_ids = selected_ids | parent_ids

    # === 2. 建库 + 复制数据 ===
    # 先复制有数据的表（copy_table 会自动建表）
    # 公共表完整复制
    public_tables = ['model_configs', 'grading_params', 'users', 'sensitive_words']
    for t in public_tables:
        n = copy_table(src, dst, t)
        print(f'  [{t}] {n} 行')

    # 题目表
    if selected_ids:
        placeholders = ', '.join(['?'] * len(selected_ids))
        n = copy_table(src, dst, 'questions', f'id IN ({placeholders})', list(selected_ids))
        print(f'  [questions] {n} 行')
    else:
        copy_table(src, dst, 'questions')
        print(f'  [questions] 0 行')

    # 关联表
    if selected_ids:
        placeholders = ', '.join(['?'] * len(selected_ids))
        related_tables = [
            ('question_answers', f'question_id IN ({placeholders})'),
            ('test_cases', f'question_id IN ({placeholders})'),
            ('rubric_script_history', f'question_id IN ({placeholders})'),
            ('grading_records', f'question_id IN ({placeholders})'),
        ]
        for table, where in related_tables:
            n = copy_table(src, dst, table, where, list(selected_ids))
            print(f'  [{table}] {n} 行')
    else:
        for table in ['question_answers', 'test_cases', 'rubric_script_history', 'grading_records']:
            copy_table(src, dst, table)
            print(f'  [{table}] 0 行')

    # 补建还没有的空表（batch_tasks / bug_log / syllabus / rubrics 等）
    create_empty_tables(dst, src)

    dst.commit()
    dst.close()

    # 统计
    dst = get_conn(dst_path)
    stats = {}
    for t in ['questions', 'question_answers', 'test_cases', 'grading_records', 'rubric_script_history']:
        cur = dst.cursor()
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        stats[t] = cur.fetchone()[0]
    # 区分父题和子题
    cur.execute('SELECT COUNT(*) FROM questions WHERE parent_id IS NULL')
    stats['parent_questions'] = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM questions WHERE parent_id IS NOT NULL')
    stats['child_questions'] = cur.fetchone()[0]
    dst.close()

    print(f'\n  >>> {dst_path}')
    print(f'  筛选策略: {tier}')
    print(f'  父题: {stats["parent_questions"]}, 子题: {stats["child_questions"]}, '
          f'满分答案: {stats["question_answers"]}, 测试用例: {stats["test_cases"]}, '
          f'评分记录: {stats["grading_records"]}, 脚本历史: {stats["rubric_script_history"]}')
    return stats


def main():
    if not os.path.exists(SRC_DB):
        print(f'错误: 生产数据库不存在: {SRC_DB}')
        sys.exit(1)

    print(f'源数据库: {SRC_DB}')
    src = get_conn(SRC_DB)

    # 先初始化所有表结构（确保目标库有完整表结构）
    src_cur = src.cursor()
    src_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in src_cur.fetchall()]
    print(f'源库共 {len(all_tables)} 张表: {", ".join(all_tables)}\n')

    for subject in SUBJECTS:
        print(f'=== 构建 {subject} 测试库 ===')
        build_subject_db(subject, src, PROJECT_ROOT)
        print()

    src.close()
    print('全部完成！')


if __name__ == '__main__':
    main()
