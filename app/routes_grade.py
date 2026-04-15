"""
单题评分 + 模型列表
路由：/providers, /grade, /models/available
"""
import json
import re
from flask import request, jsonify, session
from loguru import logger
from app.api_shared import (
    api_bp, grading_engine, PROVIDER_NAMES, _check_subject_access,
)
from app.models.db_models import (
    add_question, get_question,
    add_grading_record,
    check_sensitive_words, get_previous_grade, log_bug,
    get_question_answers, get_grading_param, get_child_questions,
)
from app.models.registry import model_registry


@api_bp.route('/providers', methods=['GET'])
def list_enabled_providers():
    """列出所有已启用的 provider 及其子模型，供前端选择"""
    from app.models.db_models import get_effective_config
    providers = []
    for pid in ('qwen', 'glm', 'ernie', 'doubao', 'xiaomi_mimimo', 'minimax', 'spark'):
        cfg = get_effective_config(pid)
        if cfg.get("enabled") and cfg.get("api_key"):
            available = cfg.get("available_models", [])
            enabled_models = set(cfg.get("extra_config", {}).get("enabled_models", []))
            all_enabled = not enabled_models
            if available:
                for m in available:
                    is_enabled = all_enabled or m["id"] in enabled_models
                    is_selected = pid == getattr(grading_engine, '_selected_provider', '') and m["id"] == getattr(grading_engine, 'model', '')
                    providers.append({
                        "id": pid + '/' + m["id"],
                        "provider": pid,
                        "model": m["id"],
                        "name": PROVIDER_NAMES.get(pid, pid),
                        "display_name": m.get("name", m["id"]),
                        "active": is_enabled,
                        "selected": is_selected,
                    })
            else:
                providers.append({
                    "id": pid + '/' + cfg.get("model", ""),
                    "provider": pid,
                    "model": cfg.get("model", ""),
                    "name": PROVIDER_NAMES.get(pid, pid),
                    "display_name": cfg.get("model", ""),
                    "active": False,
                })
    return jsonify({"success": True, "data": providers})


def _load_question_for_grading(data):
    """从请求数据加载题目信息，返回 (question_text, rubric, max_score, subject, question_answers_list, scoring_strategy, question_id)"""
    question_id = data.get('question_id') or data.get('questionId')
    rubric = data.get('rubric', {})
    question_text = data.get('question', '')
    max_score = data.get('max_score', 10.0)
    subject = data.get('subject', 'general')
    question_answers_list = []
    scoring_strategy = 'avg'
    q = None

    if question_id:
        q = get_question(int(question_id))
        if q:
            if not _check_subject_access(q.get('subject', '')):
                return None, None, None, None, None, None, None  # 权限拒绝
            question_text = q.get('content') or question_text
            max_score = q.get('max_score') or max_score
            if q.get('subject'):
                subject = q['subject']
            # 子题注入父题阅读材料
            if q.get('parent_id'):
                parent = get_question(int(q['parent_id']))
                if parent and parent.get('content'):
                    question_text = f"[Reading Material / 阅读材料]\n{parent['content']}\n\n[Question / 题目]\n{question_text}"
            # 注入 rubric 字段
            if not rubric:
                rubric = {}
            if q.get('rubric_script'):
                rubric['rubricScript'] = q['rubric_script']
            if q.get('rubric_rules'):
                rubric['rubricRules'] = q['rubric_rules']
            if q.get('rubric_points'):
                rubric['rubricPoints'] = q['rubric_points']
            if q.get('standard_answer'):
                rubric['standardAnswer'] = q['standard_answer']
            if q.get('rubric'):
                try:
                    db_rubric = json.loads(q['rubric']) if isinstance(q['rubric'], str) else q['rubric']
                    if isinstance(db_rubric, dict):
                        for k, v in db_rubric.items():
                            if k not in rubric or not rubric[k]:
                                rubric[k] = v
                except Exception:
                    pass
            # 加载满分答案列表
            question_answers_list = get_question_answers(int(question_id))
            # 英语父题：额外加载子题的采分点
            if q.get('subject') == 'english' and not q.get('parent_id'):
                children = get_child_questions(int(question_id))
                for child in children:
                    child_answers = get_question_answers(child['id'])
                    question_answers_list.extend(child_answers)
            # 评分策略
            if q.get('scoring_strategy'):
                scoring_strategy = q['scoring_strategy']
            else:
                scoring_strategy = get_grading_param('scoring_strategy', 'avg') or 'avg'

    return question_text, rubric, max_score, subject, question_answers_list, scoring_strategy, question_id


@api_bp.route('/grade', methods=['POST'])
def grade_answer():
    """单题智能评分"""
    data = request.json
    student_answer = data.get('answer', '')
    student_id = data.get('student_id', '')
    student_name = data.get('student_name', '')
    exam_name = data.get('exam_name', '')
    provider = data.get('provider')
    model = data.get('model')

    # 加载题目信息
    question_text, rubric, max_score, subject, question_answers_list, scoring_strategy, question_id = _load_question_for_grading(data)

    # 权限拒绝
    if question_text is None:
        return jsonify({'success': False, 'error': '无权评分其他科目的题目'}), 403

    # 非 question_id 模式：校验直接传的 subject
    if not question_id and not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权评分其他科目的题目'}), 403

    # 空答案前置拦截
    from app.english_prompts import is_empty_answer_en, is_short_answer_en
    is_empty = False
    if subject == 'english':
        is_empty = is_empty_answer_en(student_answer)
    else:
        stripped = re.sub(r'[\s\W]+', '', student_answer)
        if len(stripped) < 2:
            is_empty = True
    if is_empty:
        record_id = add_grading_record(
            question_id=question_id, student_answer=student_answer, score=0,
            details=json.dumps({"final_score": 0, "comment": "考生未作答", "scoring_items": [], "needs_review": False, "warning": "答案为空或仅含标点，系统直接判0分"}, ensure_ascii=False),
            model_used='precheck', confidence=1.0,
            student_id=student_id or None, student_name=student_name or None, exam_name=exam_name or None
        )
        return jsonify({'success': True, 'data': {'record_id': record_id, 'score': 0, 'confidence': 1.0, 'comment': '考生未作答', 'details': {'final_score': 0, 'comment': '考生未作答', 'scoring_items': [], 'needs_review': False, 'warning': '答案为空或仅含标点，系统直接判0分'}, 'model_used': 'precheck', 'needs_review': False, 'warning': '答案为空或仅含标点，系统直接判0分'}})

    # 敏感词扫描
    sensitive_hits = check_sensitive_words(student_answer, subject)
    high_hits = [h for h in sensitive_hits if h.get('severity') == 'high']
    if high_hits:
        hit_words = '、'.join(h['word'] for h in high_hits)
        log_bug(bug_type='sensitive_word', description=f'答案触发敏感词：{hit_words}', details=json.dumps([h.get('word','') for h in high_hits], ensure_ascii=False), question_id=question_id, model_used='sensitive_filter')
        record_id = add_grading_record(
            question_id=question_id, student_answer=student_answer, score=0,
            details=json.dumps({"final_score": 0, "comment": "答案触发敏感词，系统直接判0分", "scoring_items": [], "needs_review": True, "warning": f"触发敏感词：{hit_words}"}, ensure_ascii=False),
            model_used='sensitive_filter', confidence=1.0,
            grading_flags=json.dumps([{"type": "sensitive_word", "severity": "error", "desc": f"触发敏感词：{hit_words}"}], ensure_ascii=False),
            student_id=student_id or None, student_name=student_name or None, exam_name=exam_name or None
        )
        return jsonify({'success': True, 'data': {'record_id': record_id, 'score': 0, 'confidence': 1.0, 'comment': '答案触发敏感词，系统直接判0分', 'details': {'final_score': 0, 'comment': '答案触发敏感词，系统直接判0分', 'scoring_items': [], 'needs_review': True, 'warning': f'触发敏感词：{hit_words}'}, 'model_used': 'sensitive_filter', 'needs_review': True, 'warning': f'触发敏感词：{hit_words}', 'grading_flags': [{"type": "sensitive_word", "severity": "error", "desc": f"触发敏感词：{hit_words}"}]}})

    # 三层并行评分
    from app.three_layer_grader import three_layer_grade
    from app.qwen_engine import QwenGradingResult
    grade_result = three_layer_grade(
        grading_engine=grading_engine, question=question_text, answer=student_answer,
        rubric=rubric, max_score=max_score, subject=subject,
        question_answers=question_answers_list, strategy=scoring_strategy,
        provider=provider, model=model,
    )
    result = grade_result['llm_result']
    layer_scores = grade_result['layer_scores']
    final_score = grade_result['final_score']

    # 英语采分点精确命中时，llm_result 为 None
    if result is None and subject == 'english':
        sp_detail = grade_result['layer_details'].get('keyword', {})
        sp_score = layer_scores.get('keyword', 0)
        if sp_score is not None and sp_score > 0:
            result = QwenGradingResult(
                final_score=sp_score, confidence=0.95, strategy='scoring_point_match',
                total_score=max_score, comment=sp_detail.get('comment', f'命中采分点，得{sp_score}分。'),
                needs_review=False, scoring_items=sp_detail.get('scoring_items', []),
            )

    if result is None:
        result = QwenGradingResult(
            final_score=final_score if final_score is not None else 0,
            confidence=0.3, strategy='fallback', total_score=max_score,
            comment='评分过程中出现问题，得分可能不准确。',
            needs_review=True, scoring_items=[],
        )

    if final_score is not None:
        result.final_score = final_score

    # 记录异常
    if result.needs_review:
        bug_type = 'grading_failed' if result.final_score is None else 'boundary_warning'
        log_bug(bug_type=bug_type, description=result.warning or '评分异常需人工复核', details=json.dumps(result.dict(), ensure_ascii=False), question_id=question_id, model_used='qwen-agent')

    # 证据真实性验证
    grading_flags = []
    if result.scoring_items:
        for item in result.scoring_items:
            quoted = item.get("quoted_text", "")
            if quoted and quoted not in student_answer:
                grading_flags.append({"type": "fake_quote", "severity": "warning", "desc": f"评分点'{item.get('name', '')}'引用的原文不存在于学生答案中", "point_name": item.get("name", "")})
                result.needs_review = True
                if not result.warning:
                    result.warning = ""
                result.warning += f"；评分点'{item.get('name', '')}'引用原文疑似编造"

    # 判别Agent：短答案高分检测
    if result.final_score is not None and result.final_score >= max_score * 0.8:
        if subject == 'english':
            word_count = len(student_answer.split())
            if is_short_answer_en(student_answer):
                grading_flags.append({"type": "short_answer_high_score", "severity": "warning", "desc": f"答案仅{word_count}个词，但得分{result.final_score}分（满分{max_score}），请人工复核"})
                result.needs_review = True
        else:
            stripped_answer = re.sub(r'[\s\W]+', '', student_answer)
            if len(stripped_answer) < 10:
                grading_flags.append({"type": "short_answer_high_score", "severity": "warning", "desc": f"答案仅{len(stripped_answer)}个字，但得分{result.final_score}分（满分{max_score}），请人工复核"})
                result.needs_review = True

    # 判别Agent：全满分检测
    if result.final_score is not None and result.final_score >= max_score * 0.95:
        if result.scoring_items and len(result.scoring_items) >= 3:
            scoreable = [i for i in result.scoring_items if i.get("max_score", 0) > 0]
            if scoreable and all(i.get("hit") and i.get("score", 0) >= i.get("max_score", 0) for i in scoreable):
                grading_flags.append({"type": "all_perfect", "severity": "info", "desc": f"所有{len(scoreable)}个评分点全部满分，可能存在评分偏差，请人工复核"})
                result.needs_review = True
    if grading_flags:
        log_bug(bug_type='fake_quote', description='LLM 引用了不存在的原文', details=json.dumps(grading_flags, ensure_ascii=False), question_id=question_id, model_used='qwen-agent')

    # model_used 标识
    if result.strategy == 'scoring_point_match':
        model_used_label = 'scoring_point_match'
    elif result.strategy == 'english_fallback':
        model_used_label = 'english_fallback'
    elif result.strategy == 'fallback':
        model_used_label = 'fallback'
    else:
        model_used_label = 'qwen-agent'

    # 保存评分记录
    record_id = add_grading_record(
        question_id=question_id, student_answer=student_answer, score=result.final_score,
        details=json.dumps(result.dict(), ensure_ascii=False), model_used=model_used_label,
        confidence=result.confidence,
        grading_flags=json.dumps(grading_flags, ensure_ascii=False) if grading_flags else None,
        student_id=student_id or None, student_name=student_name or None, exam_name=exam_name or None
    )

    # 一致性校验
    if student_id and question_id and result.final_score is not None:
        prev = get_previous_grade(student_id, question_id, exclude_record_id=record_id)
        if prev and prev.get('score') is not None:
            diff = abs(result.final_score - prev['score'])
            if diff > max_score * 0.2:
                flag = {"type": "score_inconsistency", "severity": "warning", "desc": f"与上次评分({prev['score']}分)差异较大({diff:.1f}分)，可能评分不一致"}
                grading_flags.append(flag)
                result.needs_review = True
                try:
                    from app.models.db_models import get_db_connection
                    conn = get_db_connection()
                    conn.execute('UPDATE grading_records SET grading_flags = ? WHERE id = ?', (json.dumps(grading_flags, ensure_ascii=False), record_id))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    return jsonify({
        'success': True,
        'data': {
            'record_id': record_id, 'score': result.final_score, 'confidence': result.confidence,
            'comment': result.comment, 'details': result.dict(), 'model_used': model_used_label,
            'needs_review': result.needs_review, 'warning': result.warning,
            'grading_flags': grading_flags, 'layer_scores': layer_scores,
            'layer_details': grade_result.get('layer_details', {}),
            'scoring_strategy': scoring_strategy,
        }
    })


@api_bp.route('/models/available', methods=['GET'])
def available_models():
    """获取所有可用模型列表"""
    models = model_registry.list_models()
    return jsonify({"success": True, "models": models})
