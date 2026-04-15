"""
Flask 应用工厂
"""

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from loguru import logger
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_app() -> Flask:
    """创建 Flask 应用"""
    import os
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # 配置
    app.config["SECRET_KEY"] = "ai-grading-system-secret-key"
    
    # Swagger配置
    try:
        from swagger_config import SWAGGER_CONFIG
        app.config['SWAGGER'] = SWAGGER_CONFIG
        
        # 初始化Flasgger
        from flasgger import Swagger
        swagger = Swagger(app)
        logger.info("Swagger文档系统初始化成功")
    except ImportError as e:
        logger.warning(f"Swagger依赖未安装: {e}")
    except Exception as e:
        logger.error(f"Swagger初始化失败: {e}")
    
    # 扩展
    CORS(app)

    # Session 校验：所有 /api/* 必须携带有效 session（白名单除外）
    @app.before_request
    def check_session():
        from flask import request, session, jsonify
        path = request.path
        # 放行：页面路由、静态资源、登录接口
        if path in ('/login', '/admin', '/') or path.startswith('/static'):
            return None
        if path == '/api/login':
            return None
        # API 路由必须有 session
        if path.startswith('/api/'):
            if 'username' not in session:
                return jsonify(success=False, error='未登录，请先登录'), 401
        return None

    # 路由
    register_routes(app)

    # 错误处理
    register_error_handlers(app)
    
    logger.info("AI Grading System 启动成功")
    
    return app


def register_routes(app: Flask):
    """注册路由"""
    from .api_routes import api_bp
    from .config_routes import config_bp
    from flask import send_from_directory, render_template
    import os

    # 登录页面
    @app.route("/login")
    def login():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'login.html')
        resp = send_file(template_path, mimetype='text/html')
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    # 题库管理 - Vue 完整界面（直接发送文件，避免 Jinja2 解析 Vue {{ }} 语法冲突）
    @app.route("/management")
    def management():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'question-bank.html')
        resp = send_file(template_path, mimetype='text/html')
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    # 管理后台 - 管理员专属（科目管理、模型配置、Bug 清单）
    @app.route("/admin")
    def admin():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'admin.html')
        return send_file(template_path, mimetype='text/html')

    # 根路径跳转到登录页
    @app.route("/")
    def index():
        from flask import redirect
        return redirect("/login")

    # 导入题目 - 独立页面
    @app.route("/import")
    def import_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'import.html')
        return send_file(template_path, mimetype='text/html')

    # 去重处理 - 独立页面
    @app.route("/dedup")
    def dedup_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'dedup.html')
        return send_file(template_path, mimetype='text/html')

    # 题目编辑 - 独立页面
    @app.route("/question-edit")
    def question_edit_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'question-edit.html')
        return send_file(template_path, mimetype='text/html')

    # 评分工作台 - 评分脚本工具独立页
    @app.route("/rubric-workbench")
    def rubric_workbench_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'rubric-workbench.html')
        return send_file(template_path, mimetype='text/html')

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

    # AI 批量出题 - 独立页面
    @app.route("/ai-generate")
    def ai_generate_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'ai-generate.html')
        return send_file(template_path, mimetype='text/html')

    # 考试大纲 / 教材内容 - 独立页面
    @app.route("/syllabus")
    def syllabus_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'syllabus.html')
        return send_file(template_path, mimetype='text/html')

    # 导出评分脚本 - 独立页面
    @app.route("/export-rubrics")
    def export_rubrics_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'export-rubrics.html')
        return send_file(template_path, mimetype='text/html')

    # 一致检查 - 独立页面
    @app.route("/consistency-check")
    def consistency_check_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'consistency-check.html')
        return send_file(template_path, mimetype='text/html')

    # 题目详情 - 独立页面
    @app.route("/question-view")
    def question_view_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'question-view.html')
        return send_file(template_path, mimetype='text/html')

    # 题库总览 - 独立页面
    @app.route("/dashboard")
    def dashboard_page():
        from flask import send_file
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'dashboard.html')
        return send_file(template_path, mimetype='text/html')

    # 注册蓝图
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
