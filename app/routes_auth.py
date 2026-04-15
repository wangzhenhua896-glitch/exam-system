"""
登录/登出 API
"""
from flask import request, jsonify, session
from app.api_routes import api_bp  # 最终改为 from app.api_shared
from app.models.db_models import get_user


@api_bp.route('/login', methods=['POST'])
def login():
    """建立 session，验证用户存在于 users 表"""
    data = request.get_json(force=True)
    username = data.get('username', '').strip()
    if not username:
        return jsonify(success=False, error='用户名不能为空'), 400
    user = get_user(username)
    if not user:
        return jsonify(success=False, error='用户不存在'), 404
    if not user.get('is_active', 1):
        return jsonify(success=False, error='用户已禁用'), 403
    session['username'] = user['username']
    session['subject'] = user.get('subject')
    session['role'] = user.get('role', 'teacher')
    return jsonify(success=True, data={
        'username': user['username'],
        'subject': user.get('subject'),
        'role': user.get('role', 'teacher'),
        'display_name': user.get('display_name', ''),
    })


@api_bp.route('/logout', methods=['POST'])
def logout():
    """清除 session"""
    session.clear()
    return jsonify(success=True)
