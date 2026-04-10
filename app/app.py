"""
Flask 应用工厂
"""

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from loguru import logger


def create_app() -> Flask:
    """创建 Flask 应用"""
    import os
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # 配置
    app.config["SECRET_KEY"] = "ai-grading-system-secret-key"
    
    # 扩展
    CORS(app)
    
    # 路由
    register_routes(app)
    
    # 错误处理
    register_error_handlers(app)
    
    logger.info("AI Grading System 启动成功")
    
    return app


def register_routes(app: Flask):
    """注册路由"""
    from .routes import grading_bp
    from .batch_routes import batch_bp
    from .validation_routes import validation_bp
    from .tuning_routes import tuning_bp
    from .api_routes import api_bp
    from .config_routes import config_bp
    from flask import send_from_directory, render_template
    import os

    # 登录页面
    @app.route("/login")
    def login():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'login.html')
        return send_file(template_path, mimetype='text/html')

    # 题库管理 - Vue 完整界面（直接发送文件，避免 Jinja2 解析 Vue {{ }} 语法冲突）
    @app.route("/management")
    def management():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'question-bank.html')
        return send_file(template_path, mimetype='text/html')

    # 根路径跳转到登录页
    @app.route("/")
    def index():
        from flask import redirect
        return redirect("/login")

    # 聚焦单题评分 - 深色主题纯净界面
    @app.route("/grading")
    def grading():
        dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dist')
        return send_from_directory(dist_dir, 'index.html')

    # 测试集管理 - 独立页面
    @app.route("/test-cases")
    def test_cases_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'test-cases.html')
        return send_file(template_path, mimetype='text/html')

    # 敏感词管理 - 独立页面
    @app.route("/sensitive-words")
    def sensitive_words_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'sensitive-words.html')
        return send_file(template_path, mimetype='text/html')

    # 用户管理 - 独立页面
    @app.route("/user-management")
    def user_management_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'user-management.html')
        return send_file(template_path, mimetype='text/html')

    # 评分引擎源码查看
    @app.route("/code-viewer")
    def code_viewer():
        return send_from_directory(static_dir, 'code-viewer.html')

    # 注册蓝图
    app.register_blueprint(grading_bp, url_prefix="/api/grading")
    app.register_blueprint(batch_bp, url_prefix="/api/batch")
    app.register_blueprint(validation_bp, url_prefix="/api/validation")
    app.register_blueprint(tuning_bp, url_prefix="/api/tuning")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api/config")


def register_error_handlers(app: Flask):
    """注册错误处理器"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "请求错误", "message": str(error)}), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "未找到", "message": str(error)}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "服务器错误", "message": str(error)}), 500
