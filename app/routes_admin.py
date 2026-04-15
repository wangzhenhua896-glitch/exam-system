"""
敏感词管理 + 用户管理 API
"""
from flask import request, jsonify, session
from app.api_shared import api_bp
from app.api_shared import _session_subject
from app.models.db_models import (
    get_sensitive_words, add_sensitive_word, update_sensitive_word,
    delete_sensitive_word, batch_add_sensitive_words,
    get_users, get_user, add_user as db_add_user, update_user, delete_user,
)
from loguru import logger


# ==================== 敏感词管理 API ====================

@api_bp.route('/sensitive-words', methods=['GET'])
def list_sensitive_words():
    """获取敏感词列表 — 非 admin 强制用 session.subject 过滤"""
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj  # 科目老师只看本科目
    else:
        subject = request.args.get('subject', '').strip() or None  # admin 可选过滤
    category = request.args.get('category', '').strip() or None
    severity = request.args.get('severity', '').strip() or None
    keyword = request.args.get('keyword', '').strip() or None
    words = get_sensitive_words(subject=subject, category=category,
                                keyword=keyword, severity=severity)
    return jsonify({'success': True, 'data': words})


@api_bp.route('/sensitive-words', methods=['POST'])
def create_sensitive_word():
    """添加敏感词 — 非 admin 强制 subject = session.subject"""
    data = request.json
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'success': False, 'message': '敏感词不能为空'}), 400
    subject = data.get('subject', 'all')
    if session.get('role') != 'admin':
        subject = session.get('subject') or 'all'
    word_id = add_sensitive_word(
        word=word,
        subject=subject,
        category=data.get('category', 'politics'),
        severity=data.get('severity', 'high')
    )
    return jsonify({'success': True, 'data': {'id': word_id}})


@api_bp.route('/sensitive-words/<int:word_id>', methods=['PUT'])
def modify_sensitive_word(word_id):
    """更新敏感词"""
    data = request.json
    ok = update_sensitive_word(word_id, **data)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '更新失败'}), 400


@api_bp.route('/sensitive-words/<int:word_id>', methods=['DELETE'])
def remove_sensitive_word(word_id):
    """删除敏感词"""
    ok = delete_sensitive_word(word_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '删除失败'}), 404


@api_bp.route('/sensitive-words/batch', methods=['POST'])
def batch_import_sensitive_words():
    """批量导入敏感词 — 非 admin 强制 subject = session.subject"""
    data = request.json
    words = data.get('words', [])
    if not words:
        return jsonify({'success': False, 'message': '导入列表为空'}), 400
    session_subj = session.get('subject') if session.get('role') != 'admin' else None
    # 支持纯文本格式（每行一个词）
    if isinstance(words, str):
        lines = [l.strip() for l in words.strip().split('\n') if l.strip()]
        words = [{'word': l, 'subject': session_subj or data.get('subject', 'all'),
                  'category': data.get('category', 'politics'),
                  'severity': data.get('severity', 'high')} for l in lines]
    elif session_subj:
        # 非 admin：覆盖每项的 subject
        words = [dict(w, subject=session_subj) for w in words]
    count = batch_add_sensitive_words(words)
    return jsonify({'success': True, 'data': {'imported': count}})


# ==================== 用户管理 ====================

@api_bp.route('/users', methods=['GET'])
def list_users():
    """获取用户列表"""
    users = get_users()
    return jsonify({'success': True, 'data': users})


@api_bp.route('/users', methods=['POST'])
def create_user():
    """新增用户"""
    data = request.json
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400
    if get_user(username):
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    user_id = db_add_user(
        username=username,
        display_name=data.get('display_name', ''),
        role=data.get('role', 'teacher'),
        subject=data.get('subject')
    )
    return jsonify({'success': True, 'data': {'id': user_id}})


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
def modify_user(user_id):
    """更新用户"""
    data = request.json
    ok = update_user(user_id, **data)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '更新失败'}), 400


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
def remove_user(user_id):
    """删除用户"""
    ok = delete_user(user_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '删除失败'}), 404
