"""
AI Grading System - 主入口
"""

import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.app import create_app
from loguru import logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AI 智能评分系统')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5001)),
                        help='监听端口 (默认: 5001 或环境变量 PORT)')
    parser.add_argument('--host', type=str, default=os.environ.get('HOST', '0.0.0.0'),
                        help='监听地址 (默认: 0.0.0.0 或环境变量 HOST)')
    parser.add_argument('--debug', action='store_true', default=None,
                        help='开启调试模式')
    parser.add_argument('--no-debug', action='store_true',
                        help='关闭调试模式')
    args = parser.parse_args()

    # 确定 debug 模式
    if args.debug:
        debug = True
    elif args.no_debug:
        debug = False
    else:
        debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')

    # 配置日志
    log_dir = os.environ.get('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    logger.add(f"{log_dir}/grading_{{time}}.log", rotation="1 day", retention="7 days")

    app = create_app()

    logger.info("🚀 AI 智能评分系统启动")
    logger.info(f"📍 地址：http://localhost:{args.port}")
    logger.info(f"🔧 调试模式：{'开启' if debug else '关闭'}")

    app.run(host=args.host, port=args.port, debug=debug)


if __name__ == "__main__":
    main()
