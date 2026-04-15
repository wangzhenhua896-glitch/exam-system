"""去重/合并 API"""
from flask import request, jsonify
from app.api_routes import api_bp
from app.api_shared import _session_subject, _check_subject_access
from app.models.db_models import get_questions, get_db_connection
from loguru import logger


@api_bp.route('/questions/find-duplicates', methods=['POST'])
def find_duplicates():
    """扫描重复题目 — 非 admin 只扫本科目"""
    import re
    from difflib import SequenceMatcher

    subject = _session_subject()  # admin 返回 None → 全部
    questions = get_questions(subject)
    if len(questions) < 2:
        return jsonify({'success': True, 'data': [], 'total_groups': 0, 'total_duplicates': 0})

    def normalize(text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', '', text)
        return text.strip()

    # 按 subject 分组，组内两两比较
    by_subject = {}
    for q in questions:
        s = q.get('subject', '')
        by_subject.setdefault(s, []).append(q)

    visited = set()
    groups = []
    group_id = 0

    # 比较的字段列表（按权重）
    COMPARE_FIELDS = ['content', 'standard_answer', 'rubric_points', 'rubric_rules', 'original_text']

    def multi_field_similarity(q1, q2):
        """综合比较多个字段，返回加权相似度"""
        ratios = []
        for field in COMPARE_FIELDS:
            t1 = normalize(q1.get(field, ''))
            t2 = normalize(q2.get(field, ''))
            if not t1 and not t2:
                continue
            if not t1 or not t2:
                ratios.append(0.0)
                continue
            ratios.append(SequenceMatcher(None, t1, t2).ratio())
        if not ratios:
            return 0.0
        # content 权重 0.4，其他字段均分 0.6
        if len(ratios) == 1:
            return ratios[0]
        content_weight = 0.4
        other_weight = 0.6 / (len(ratios) - 1) if len(ratios) > 1 else 0
        result = 0
        for idx, r in enumerate(ratios):
            if idx == 0:
                result += r * content_weight
            else:
                result += r * other_weight
        return result

    for subject, qs in by_subject.items():
        for i, q1 in enumerate(qs):
            if q1['id'] in visited:
                continue
            dupes = [q1]
            has_content = normalize(q1.get('content', ''))
            if not has_content:
                continue
            for j in range(i + 1, len(qs)):
                q2 = qs[j]
                if q2['id'] in visited:
                    continue
                has_c2 = normalize(q2.get('content', ''))
                if not has_c2:
                    continue
                ratio = multi_field_similarity(q1, q2)
                if ratio > 0.75:
                    dupes.append(q2)
            if len(dupes) > 1:
                group_id += 1
                for d in dupes:
                    visited.add(d['id'])

                # 判断是否完全相同（所有比较字段的 normalized 值都一致）
                is_exact = True
                for field in COMPARE_FIELDS:
                    vals = set(normalize(q.get(field, '')) for q in dupes if normalize(q.get(field, '')))
                    if len(vals) > 1:
                        is_exact = False
                        break

                # 生成最优字段组合建议
                suggestion = _build_merge_suggestion(dupes)
                groups.append({
                    'group_id': group_id,
                    'exact': is_exact,
                    'questions': [{
                        'id': q['id'],
                        'question_number': q.get('question_number'),
                        'content': (q.get('content') or '')[:80],
                        'original_text': (q.get('original_text') or '')[:80],
                        'max_score': q.get('max_score'),
                        'standard_answer': (q.get('standard_answer') or '')[:60],
                        'rubric_points': (q.get('rubric_points') or '')[:60],
                        'rubric_rules': (q.get('rubric_rules') or '')[:60],
                        'rubric_script': (q.get('rubric_script') or '')[:60],
                        'quality_score': q.get('quality_score'),
                        'created_at': q.get('created_at'),
                    } for q in dupes],
                    'suggestion': suggestion,
                })

    return jsonify({
        'success': True,
        'data': groups,
        'total_groups': len(groups),
        'total_duplicates': sum(len(g['questions']) for g in groups),
    })


def _build_merge_suggestion(dupes):
    """从一组重复题中为每个字段选最优来源"""
    import re

    def calc_real_score(q):
        """从 rubric_points / standard_answer 计算实际总分"""
        text = (q.get('rubric_points') or '') + '\n' + (q.get('standard_answer') or '')
        scores = re.findall(r'[(（](\d+\.?\d*)\s*(分|points?|marks?)', text)
        if scores:
            return round(sum(float(s) for s in scores), 1)
        return q.get('max_score', 10.0)

    def best_longest(field):
        """选字段值最长的"""
        best = None
        for q in dupes:
            val = (q.get(field) or '').strip()
            if val and (best is None or len(val) > len(best['value'])):
                best = {'value': val, 'from_id': q['id']}
        return best

    def best_nonempty_prefer_newer(field):
        """选有值的，多个选 id 最大的"""
        best = None
        for q in dupes:
            val = (q.get(field) or '').strip()
            if val and (best is None or q['id'] > best['from_id']):
                best = {'value': val, 'from_id': q['id']}
        return best

    def best_value(field, key_fn):
        """选 key_fn(val) 最大的"""
        best = None
        for q in dupes:
            val = q.get(field)
            if val is not None and (best is None or key_fn(val) > key_fn(best['value'])):
                best = {'value': val, 'from_id': q['id']}
        return best

    # 题干 → 选最长
    content = best_longest('content')
    # 原题（原始未处理）→ 选最长
    original_text = best_longest('original_text')
    # 标准答案 → 选最长
    standard_answer = best_longest('standard_answer')
    # 评分规则 → 有值优先，多个选更新的
    rubric_rules = best_nonempty_prefer_newer('rubric_rules')
    # 评分要点 → 有值优先，多个选更新的
    rubric_points = best_nonempty_prefer_newer('rubric_points')
    # 评分脚本 → 有值优先，多个选更新的
    rubric_script = best_nonempty_prefer_newer('rubric_script')
    # 题号 → 有值优先
    question_number = best_nonempty_prefer_newer('question_number')
    # 质量评分 → 选最高
    quality_score = best_value('quality_score', lambda v: v or 0)
    # 分值 → 从 rubric_points/standard_answer 计算
    max_score = None
    for q in dupes:
        ms = calc_real_score(q)
        if ms and (max_score is None or ms != 10.0):
            max_score = {'value': ms, 'from_id': q['id']}
    if max_score is None:
        max_score = {'value': 10.0, 'from_id': dupes[0]['id']}

    # keep_as_base: 优先有 rubric_script 的，否则 id 最大的
    base = max(dupes, key=lambda q: (bool(q.get('rubric_script')), q['id']))

    result = {
        'content': content,
        'original_text': original_text,
        'standard_answer': standard_answer,
        'rubric_rules': rubric_rules,
        'rubric_points': rubric_points,
        'rubric_script': rubric_script,
        'question_number': question_number,
        'quality_score': quality_score,
        'max_score': max_score,
        'keep_as_base': base['id'],
        'delete_ids': [q['id'] for q in dupes if q['id'] != base['id']],
    }
    return result


@api_bp.route('/questions/merge', methods=['POST'])
def merge_questions():
    """合并重复题目：更新保留题目字段，迁移关联数据，删除多余题目"""
    import sqlite3
    data = request.json or {}
    keep_id = data.get('keep_id')
    delete_ids = data.get('delete_ids', [])
    update_fields = data.get('update_fields', {})

    if not keep_id or not delete_ids:
        return jsonify({'success': False, 'error': '参数不完整'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 更新保留题目的字段
        if update_fields:
            set_clauses = []
            values = []
            for key in ['content', 'original_text', 'standard_answer', 'rubric_rules', 'rubric_points',
                        'rubric_script', 'max_score', 'question_number', 'quality_score']:
                if key in update_fields:
                    set_clauses.append(f'{key} = ?')
                    values.append(update_fields[key])
            if set_clauses:
                set_clauses.append('updated_at = CURRENT_TIMESTAMP')
                values.append(keep_id)
                cursor.execute(
                    f"UPDATE questions SET {', '.join(set_clauses)} WHERE id = ?",
                    values
                )

        # 2. 迁移关联数据 + 3. 删除重复题目
        deleted = 0
        for del_id in delete_ids:
            if del_id == keep_id:
                continue
            cursor.execute('UPDATE grading_records SET question_id = ? WHERE question_id = ?',
                           (keep_id, del_id))
            cursor.execute('UPDATE test_cases SET question_id = ? WHERE question_id = ?',
                           (keep_id, del_id))
            cursor.execute('UPDATE rubric_script_history SET question_id = ? WHERE question_id = ?',
                           (keep_id, del_id))
            cursor.execute('DELETE FROM questions WHERE id = ?', (del_id,))
            deleted += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'success': True, 'deleted': deleted, 'keep_id': keep_id})


@api_bp.route('/questions/find-same-number', methods=['POST'])
def find_same_number():
    """按题号分组 — 非 admin 只扫本科目"""
    subject = _session_subject()  # admin 返回 None → 全部
    questions = get_questions(subject)
    if len(questions) < 2:
        return jsonify({'success': True, 'data': [], 'total_groups': 0})

    # 按 question_number 分组
    by_number = {}
    for q in questions:
        num = (q.get('question_number') or '').strip()
        if not num:
            continue
        by_number.setdefault(num, []).append(q)

    import re

    def normalize(text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', '', text)
        return text.strip()

    COMPARE_FIELDS = ['content', 'standard_answer', 'rubric_points', 'rubric_rules', 'original_text']

    groups = []
    for num, qs in sorted(by_number.items()):
        if len(qs) < 2:
            continue

        # 判断是否完全相同
        is_exact = True
        for field in COMPARE_FIELDS:
            vals = [normalize(q.get(field, '')) for q in qs]
            if len(set(vals)) > 1:
                is_exact = False
                break

        suggestion = _build_merge_suggestion(qs)
        groups.append({
            'group_id': f'num_{num}',
            'question_number': num,
            'exact': is_exact,
            'questions': [{
                'id': q['id'],
                'content': (q.get('content') or '')[:200],
                'original_text': (q.get('original_text') or '')[:200],
                'standard_answer': (q.get('standard_answer') or '')[:200],
                'rubric_rules': (q.get('rubric_rules') or '')[:200],
                'rubric_points': (q.get('rubric_points') or '')[:200],
                'rubric_script': (q.get('rubric_script') or '')[:200],
                'max_score': q.get('max_score'),
                'quality_score': q.get('quality_score'),
                'question_number': q.get('question_number'),
            } for q in qs],
            'suggestion': suggestion,
        })

    return jsonify({'success': True, 'data': groups, 'total_groups': len(groups)})
