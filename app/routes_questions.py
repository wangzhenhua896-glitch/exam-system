"""
题目 CRUD + 答案管理 + 评分参数 + 父子题查询
"""
import json
from flask import request, jsonify, session
from app.api_shared import api_bp, _check_subject_access, _session_subject
from app.models.db_models import (
    add_question, get_questions, get_question,
    update_question, delete_question,
    get_question_answers, add_question_answer,
    update_question_answer, delete_question_answer,
    get_grading_param, get_all_grading_params, set_grading_param,
    get_child_questions, get_question_with_children,
    get_script_history,
)
from loguru import logger


@api_bp.route('/questions', methods=['GET'])
def list_questions():
    """获取题目列表 — 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject()  # admin 返回 None → 全部；teacher 返回本科目
    if subject is None:
        subject = request.args.get('subject')  # admin 可选过滤
    questions = get_questions(subject)
    # 转换rubric字符串为对象
    for q in questions:
        if isinstance(q.get('rubric'), str):
            try:
                q['rubric'] = json.loads(q['rubric'])
            except:
                pass
    return jsonify({'success': True, 'data': questions})


@api_bp.route('/questions/<int:question_id>', methods=['GET'])
def get_question_detail(question_id):
    """获取题目详情"""
    question = get_question(question_id)
    if not question:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(question.get('subject', '')):
        return jsonify({'success': False, 'error': '无权访问其他科目的题目'}), 403
    if isinstance(question.get('rubric'), str):
        try:
            question['rubric'] = json.loads(question['rubric'])
        except:
            pass
    # 解析 workflow_status JSON 字符串
    if isinstance(question.get('workflow_status'), str):
        try:
            question['workflow_status'] = json.loads(question['workflow_status'])
        except:
            pass
    # 添加评分脚本版本信息
    history = get_script_history(question_id)
    question['script_version'] = history[0]['version'] if history else 0
    question['script_version_count'] = len(history)
    return jsonify({'success': True, 'data': question})


@api_bp.route('/questions', methods=['POST'])
def create_question():
    """创建新题目 — 非 admin 强制 subject = session.subject"""
    data = request.json
    rubric = data.get('rubric')
    if isinstance(rubric, dict):
        rubric = json.dumps(rubric, ensure_ascii=False)

    subject = data.get('subject', 'general')
    if not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权为其他科目创建题目'}), 403

    question_id = add_question(
        subject=subject,
        title=data.get('title', ''),
        content=data.get('content', ''),
        original_text=data.get('original_text'),
        standard_answer=data.get('standard_answer'),
        rubric_rules=data.get('rubric_rules'),
        rubric_points=data.get('rubric_points'),
        rubric_script=data.get('rubric_script'),
        rubric=rubric,
        max_score=data.get('max_score', 10.0),
        quality_score=data.get('quality_score'),
        question_number=data.get('question_number'),
        difficulty=data.get('difficulty'),
        exam_name=data.get('exam_name'),
        parent_id=data.get('parent_id'),
        scoring_strategy=data.get('scoring_strategy'),
        content_html=data.get('content_html'),
        question_type=data.get('question_type', 'essay'),
        workflow_status=data.get('workflow_status')
    )
    return jsonify({'success': True, 'data': {'id': question_id}})


@api_bp.route('/questions/<int:question_id>', methods=['PUT'])
def update_question_detail(question_id):
    """更新题目 — 非 admin 不能改其他科目题目"""
    existing = get_question(question_id)
    if not existing:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(existing.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的题目'}), 403

    data = request.json
    rubric = data.get('rubric')
    if isinstance(rubric, dict):
        rubric = json.dumps(rubric, ensure_ascii=False)
    if not rubric:
        rubric = existing.get('rubric', '{}')

    success = update_question(
        question_id,
        subject=data.get('subject', existing.get('subject', 'general')),
        title=data.get('title', ''),
        content=data.get('content', ''),
        original_text=data.get('original_text'),
        standard_answer=data.get('standard_answer'),
        rubric_rules=data.get('rubric_rules'),
        rubric_points=data.get('rubric_points'),
        rubric_script=data.get('rubric_script'),
        rubric=rubric,
        max_score=data.get('max_score', 10.0),
        quality_score=data.get('quality_score'),
        parent_id=data.get('parent_id'),
        scoring_strategy=data.get('scoring_strategy'),
        content_html=data.get('content_html'),
        question_type=data.get('question_type'),
        workflow_status=data.get('workflow_status')
    )
    if not success:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    return jsonify({'success': True, 'data': {'id': question_id}})


@api_bp.route('/questions/<int:question_id>/workflow-status', methods=['PUT'])
def update_question_workflow_status(question_id):
    """轻量更新 workflow_status（不触发脚本快照）"""
    from app.models.db_models import update_workflow_status
    # 科目访问控制
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的题目'}), 403
    data = request.json or {}
    ws = data.get('workflow_status')
    if ws is None:
        return jsonify({'success': False, 'error': 'workflow_status 不能为空'}), 400
    if isinstance(ws, dict):
        ws = json.dumps(ws, ensure_ascii=False)
    success = update_workflow_status(question_id, ws)
    if not success:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    return jsonify({'success': True})


@api_bp.route('/questions/<int:question_id>', methods=['DELETE'])
def delete_question_detail(question_id):
    """删除题目 — 非 admin 不能删其他科目题目"""
    question = get_question(question_id)
    if not question:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(question.get('subject', '')):
        return jsonify({'success': False, 'error': '无权删除其他科目的题目'}), 403
    success = delete_question(question_id)
    if not success:
        return jsonify({'success': False, 'error': '删除失败'}), 500
    return jsonify({'success': True, 'data': {'id': question_id}})


# ==================== 满分答案管理 ====================

@api_bp.route('/questions/<int:question_id>/answers', methods=['GET'])
def list_question_answers(question_id):
    """获取某题的满分答案列表"""
    # 科目访问控制
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权访问其他科目的答案'}), 403
    scope_type = request.args.get('scope_type')
    answers = get_question_answers(question_id, scope_type)
    return jsonify({'success': True, 'data': answers})


@api_bp.route('/questions/<int:question_id>/answers', methods=['POST'])
def create_question_answer(question_id):
    """为某题添加一个满分答案"""
    # 科目访问控制
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的答案'}), 403
    data = request.json or {}
    answer_id = add_question_answer(
        question_id=question_id,
        scope_type=data.get('scope_type', 'question'),
        scope_id=data.get('scope_id', ''),
        score_ratio=data.get('score_ratio', 1.0),
        answer_text=data.get('answer_text', ''),
        label=data.get('label', ''),
        source=data.get('source', 'manual'),
        sort_order=data.get('sort_order', 0),
    )
    return jsonify({'success': True, 'data': {'id': answer_id}}), 201


@api_bp.route('/questions/<int:question_id>/answers/<int:answer_id>', methods=['PUT'])
def edit_question_answer(question_id, answer_id):
    """修改某个满分答案"""
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的答案'}), 403
    data = request.json or {}
    success = update_question_answer(answer_id, **data)
    if not success:
        return jsonify({'success': False, 'error': '答案不存在'}), 404
    return jsonify({'success': True, 'data': {'id': answer_id}})


@api_bp.route('/questions/<int:question_id>/answers/<int:answer_id>', methods=['DELETE'])
def remove_question_answer(question_id, answer_id):
    """删除某个满分答案"""
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权删除其他科目的答案'}), 403
    success = delete_question_answer(answer_id)
    if not success:
        return jsonify({'success': False, 'error': '答案不存在'}), 404
    return jsonify({'success': True, 'data': {'id': answer_id}})


# ==================== 评分参数配置 ====================

@api_bp.route('/grading-params', methods=['GET'])
def list_grading_params():
    """获取所有评分参数"""
    params = get_all_grading_params()
    return jsonify({'success': True, 'data': params})


@api_bp.route('/grading-params/<key>', methods=['PUT'])
def edit_grading_param(key):
    """修改某个评分参数"""
    data = request.json or {}
    value = data.get('value')
    if value is None:
        return jsonify({'success': False, 'error': 'value 必填'}), 400
    set_grading_param(key, str(value), data.get('description', ''))
    return jsonify({'success': True, 'data': {'key': key, 'value': str(value)}})


# ==================== 父子题查询 ====================

@api_bp.route('/questions/<int:question_id>/children', methods=['GET'])
def list_child_questions(question_id):
    """获取某题的子题列表"""
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权访问其他科目的题目'}), 403
    children = get_child_questions(question_id)
    return jsonify({'success': True, 'data': children})


@api_bp.route('/questions/<int:question_id>/with-children', methods=['GET'])
def get_question_detail_with_children(question_id):
    """获取题目及其子题"""
    q = get_question_with_children(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权访问其他科目的题目'}), 403
    return jsonify({'success': True, 'data': q})
