"""
统计报表 + 评分历史 + 仪表盘
路由：/history, /stats, /dashboard
"""
import json
from flask import request, jsonify
from app.api_shared import api_bp, _session_subject
from app.models.db_models import get_db_connection


@api_bp.route('/history', methods=['GET'])
def list_history():
    """获取评分历史 — 非 admin 只看本科目记录"""
    question_id = request.args.get('question_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    subject = _session_subject()

    conn = get_db_connection()
    cursor = conn.cursor()
    if question_id:
        if subject:
            cursor.execute(
                '''SELECT gr.* FROM grading_records gr
                   JOIN questions q ON gr.question_id = q.id
                   WHERE gr.question_id = ? AND q.subject = ?
                   ORDER BY gr.graded_at DESC LIMIT ?''',
                (question_id, subject, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM grading_records WHERE question_id = ? ORDER BY graded_at DESC LIMIT ?',
                (question_id, limit)
            )
    else:
        if subject:
            cursor.execute(
                '''SELECT gr.* FROM grading_records gr
                   JOIN questions q ON gr.question_id = q.id
                   WHERE q.subject = ?
                   ORDER BY gr.graded_at DESC LIMIT ?''',
                (subject, limit)
            )
        else:
            cursor.execute('SELECT * FROM grading_records ORDER BY graded_at DESC LIMIT ?', (limit,))
    columns = [desc[0] for desc in cursor.description]
    history = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    for h in history:
        if isinstance(h.get('details'), str):
            try:
                h['details'] = json.loads(h['details'])
            except Exception:
                pass
    return jsonify({'success': True, 'data': history})


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息 — 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject()
    conn = get_db_connection()
    cursor = conn.cursor()

    if subject:
        cursor.execute('SELECT COUNT(*) FROM questions WHERE subject = ?', [subject])
        total_questions = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ?
        """, [subject])
        total_gradings = cursor.fetchone()[0]
        cursor.execute("""
            SELECT AVG(gr.score) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ? AND gr.score IS NOT NULL
        """, [subject])
        avg_score = cursor.fetchone()[0] or 0
        subjects = {subject: total_questions}
    else:
        cursor.execute('SELECT COUNT(*) FROM questions')
        total_questions = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM grading_records')
        total_gradings = cursor.fetchone()[0]
        cursor.execute('SELECT AVG(score) FROM grading_records WHERE score IS NOT NULL')
        avg_score = cursor.fetchone()[0] or 0
        cursor.execute('SELECT subject, COUNT(*) FROM questions GROUP BY subject')
        subjects = dict(cursor.fetchall())

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'total_questions': total_questions,
            'total_gradings': total_gradings,
            'average_score': round(avg_score, 2),
            'subjects': subjects
        }
    })


@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """题库总览 — 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject()
    if subject is None:
        subject = request.args.get('subject', '').strip() or None
    conn = get_db_connection()
    cursor = conn.cursor()

    if subject:
        q_cond = 'WHERE subject = ?'
        q_params = [subject]
    else:
        q_cond = ''
        q_params = []

    # 1. 基础统计
    cursor.execute(f'SELECT COUNT(*) FROM questions {q_cond}', q_params)
    total_questions = cursor.fetchone()[0]

    if subject:
        total_subjects = 1
    else:
        cursor.execute('SELECT COUNT(DISTINCT subject) FROM questions')
        total_subjects = cursor.fetchone()[0]

    if subject:
        cursor.execute("""
            SELECT COUNT(*) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ?
        """, [subject])
        total_gradings = cursor.fetchone()[0]
        cursor.execute("""
            SELECT AVG(gr.score) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ? AND gr.score IS NOT NULL
        """, [subject])
    else:
        cursor.execute('SELECT COUNT(*) FROM grading_records')
        total_gradings = cursor.fetchone()[0]
        cursor.execute('SELECT AVG(score) FROM grading_records WHERE score IS NOT NULL')
    avg_score = cursor.fetchone()[0] or 0

    # 2. 各科目题目分布
    if not subject:
        cursor.execute('SELECT subject, COUNT(*) FROM questions GROUP BY subject ORDER BY COUNT(*) DESC')
        subject_dist = [{'subject': row[0], 'count': row[1]} for row in cursor.fetchall()]
    else:
        subject_dist = []

    # 3. 评分脚本覆盖率
    if subject:
        cursor.execute("""
            SELECT COUNT(*) FROM questions
            WHERE subject = ? AND rubric_script IS NOT NULL AND rubric_script != ''
        """, [subject])
    else:
        cursor.execute("SELECT COUNT(*) FROM questions WHERE rubric_script IS NOT NULL AND rubric_script != ''")
    has_script = cursor.fetchone()[0]
    no_script = total_questions - has_script

    # 4. 测试用例覆盖
    if subject:
        cursor.execute("""
            SELECT COUNT(DISTINCT tc.question_id) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id WHERE q.subject = ?
        """, [subject])
        questions_with_tc = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id WHERE q.subject = ?
        """, [subject])
        total_test_cases = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id WHERE q.subject = ? AND tc.case_type = 'ai_generated'
        """, [subject])
        tc_ai = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id WHERE q.subject = ? AND tc.case_type = 'simulated'
        """, [subject])
        tc_simulated = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id WHERE q.subject = ? AND tc.case_type = 'real'
        """, [subject])
        tc_real = cursor.fetchone()[0]
    else:
        cursor.execute('SELECT COUNT(DISTINCT question_id) FROM test_cases')
        questions_with_tc = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM test_cases')
        total_test_cases = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'ai_generated'")
        tc_ai = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'simulated'")
        tc_simulated = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'real'")
        tc_real = cursor.fetchone()[0]

    questions_without_tc = total_questions - questions_with_tc

    # 5. 质量评分分布
    quality_dist = {}
    for cond, val in [('quality_score IS NULL', 'not_evaluated'), ('quality_score < 60', 'low'), ('quality_score >= 60 AND quality_score < 80', 'medium'), ('quality_score >= 80', 'high')]:
        if subject:
            cursor.execute(f'SELECT COUNT(*) FROM questions WHERE subject = ? AND {cond}', [subject])
        else:
            cursor.execute(f'SELECT COUNT(*) FROM questions WHERE {cond}')
        quality_dist[val] = cursor.fetchone()[0]

    # 6. 最近评分趋势（最近 7 天）
    if subject:
        cursor.execute("""
            SELECT DATE(gr.graded_at) as day, COUNT(*) as cnt
            FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ? AND gr.graded_at >= DATE('now', '-7 days')
            GROUP BY DATE(gr.graded_at) ORDER BY day
        """, [subject])
    else:
        cursor.execute("""
            SELECT DATE(graded_at) as day, COUNT(*) as cnt
            FROM grading_records
            WHERE graded_at >= DATE('now', '-7 days')
            GROUP BY DATE(graded_at) ORDER BY day
        """)
    grading_trend = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

    # 7. 最近创建的题目
    cursor.execute(f'SELECT id, title, subject, created_at FROM questions {q_cond} ORDER BY created_at DESC LIMIT 5', q_params)
    recent_questions = [dict(zip(['id', 'title', 'subject', 'created_at'], row)) for row in cursor.fetchall()]

    # 8. 最近评分记录
    if subject:
        cursor.execute("""
            SELECT gr.id, gr.question_id, q.title, gr.score, gr.model_used, gr.graded_at
            FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ?
            ORDER BY gr.graded_at DESC LIMIT 5
        """, [subject])
    else:
        cursor.execute("""
            SELECT gr.id, gr.question_id, q.title, gr.score, gr.model_used, gr.graded_at
            FROM grading_records gr
            LEFT JOIN questions q ON gr.question_id = q.id
            ORDER BY gr.graded_at DESC LIMIT 5
        """)
    recent_gradings = [dict(zip(['id', 'question_id', 'title', 'score', 'model_used', 'graded_at'], row)) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'subject': subject or None,
            'overview': {
                'total_questions': total_questions,
                'total_subjects': total_subjects,
                'total_gradings': total_gradings,
                'average_score': round(avg_score, 2),
            },
            'subject_dist': subject_dist,
            'rubric_coverage': {'has_script': has_script, 'no_script': no_script},
            'test_case_coverage': {
                'questions_with_tc': questions_with_tc,
                'questions_without_tc': questions_without_tc,
                'total_cases': total_test_cases,
                'ai_generated': tc_ai,
                'simulated': tc_simulated,
                'real': tc_real,
            },
            'quality_dist': quality_dist,
            'grading_trend': grading_trend,
            'recent_questions': recent_questions,
            'recent_gradings': recent_gradings,
        }
    })
