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
    
    # 主页
    @app.route("/")
    def index():
        return render_template("index.html")
    
    # 注册蓝图
    app.register_blueprint(grading_bp, url_prefix="/api/grading")
    app.register_blueprint(batch_bp, url_prefix="/api/batch")
    app.register_blueprint(validation_bp, url_prefix="/api/validation")
    app.register_blueprint(tuning_bp, url_prefix="/api/tuning")


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
