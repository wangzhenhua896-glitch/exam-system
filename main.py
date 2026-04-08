"""
AI Grading System - 主入口
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.app import create_app
from loguru import logger

# 配置日志
logger.add("logs/grading_{time}.log", rotation="1 day", retention="7 days")


def main():
    """主函数"""
    app = create_app()
    
    logger.info("🚀 AI 智能评分系统启动")
    logger.info("📍 地址：http://localhost:5005")

    app.run(host="0.0.0.0", port=5005, debug=True)


if __name__ == "__main__":
    main()
