"""
Swagger/OpenAPI 配置
AI智能评分系统 API文档
"""

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs/",
    "title": "AI智能评分系统 API文档",
    "version": "1.0.0",
    "description": """
    # AI智能评分系统 API文档
    
    ## 产品概述
    基于大语言模型的主观题（简答题）自动评分引擎。
    可通过API对外提供评分服务，供第三方考试/教务系统集成调用。
    
    ## 主要功能
    - 单题智能评分
    - 批量评分任务
    - 题目管理
    - 评分脚本生成
    - 测试用例管理
    - 模型配置管理
    
    ## 技术栈
    - 后端: Flask 3.0.2
    - 数据库: SQLite
    - 前端: Vue 3 + Element Plus
    - 模型: 多模型支持（通义/豆包/GLM/文心等）
    
    ## 接口分类
    1. **评分接口** - 核心评分功能
    2. **题目管理** - 题库维护
    3. **测试用例** - 验证评分准确性
    4. **系统管理** - 用户、配置管理
    5. **模型管理** - AI模型配置
    
    ## 认证方式
    当前版本使用简单的用户认证，后续版本支持JWT Token。
    
    ## 错误码
    - 200: 成功
    - 400: 请求参数错误
    - 401: 未授权
    - 404: 资源不存在
    - 500: 服务器内部错误
    """,
    "termsOfService": "",
    "contact": {
        "name": "技术支持",
        "url": "http://localhost:5001",
        "email": "support@example.com"
    },
    "license": {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    "schemes": ["http", "https"],
    "host": "localhost:5001",
    "basePath": "/api",
    "tags": [
        {
            "name": "评分",
            "description": "核心评分功能"
        },
        {
            "name": "题目管理",
            "description": "题库维护功能"
        },
        {
            "name": "测试用例",
            "description": "评分准确性验证"
        },
        {
            "name": "批量任务",
            "description": "批量评分功能"
        },
        {
            "name": "系统管理",
            "description": "用户和配置管理"
        },
        {
            "name": "模型管理",
            "description": "AI模型配置"
        }
    ]
}