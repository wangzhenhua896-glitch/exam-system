# 系统配置文件

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# 国产大模型 API 配置
# =============================================================================

# 通义千问 (阿里云)
QWEN_CONFIG = {
    "api_key": os.getenv("QWEN_API_KEY", ""),
    "base_url": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "model": os.getenv("QWEN_MODEL", "qwen-max"),
    "enabled": os.getenv("QWEN_ENABLED", "true").lower() == "true",
}

# 智谱 GLM
GLM_CONFIG = {
    "api_key": os.getenv("GLM_API_KEY", ""),
    "base_url": os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    "model": os.getenv("GLM_MODEL", "glm-4"),
    "enabled": os.getenv("GLM_ENABLED", "false").lower() == "true",  # 默认禁用
}

# MiniMax
MINIMAX_CONFIG = {
    "api_key": os.getenv("MINIMAX_API_KEY", ""),
    "group_id": os.getenv("MINIMAX_GROUP_ID", ""),
    "base_url": os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
    "model": os.getenv("MINIMAX_MODEL", "abab6.5-chat"),
    "enabled": os.getenv("MINIMAX_ENABLED", "false").lower() == "true",  # 默认禁用
}

# 百度文心一言
ERNIE_CONFIG = {
    "api_key": os.getenv("ERNIE_API_KEY", ""),
    "secret_key": os.getenv("ERNIE_SECRET_KEY", ""),
    "base_url": os.getenv("ERNIE_BASE_URL", "https://aip.baidubce.com"),
    "model": os.getenv("ERNIE_MODEL", "ernie-4.0"),
    "enabled": os.getenv("ERNIE_ENABLED", "false").lower() == "true",
}

# 讯飞星火
SPARK_CONFIG = {
    "app_id": os.getenv("SPARK_APP_ID", ""),
    "api_key": os.getenv("SPARK_API_KEY", ""),
    "api_secret": os.getenv("SPARK_API_SECRET", ""),
    "model": os.getenv("SPARK_MODEL", "spark-3.5"),
    "enabled": os.getenv("SPARK_ENABLED", "false").lower() == "true",
}

# =============================================================================
# 评分系统配置
# =============================================================================

GRADING_CONFIG = {
    # 采样次数
    "sample_counts": [1, 3, 5, 7],
    "default_sample_count": int(os.getenv("DEFAULT_SAMPLE_COUNT", "3")),
    
    # 聚合策略
    "aggregation_strategies": ["majority_vote", "weighted_average", "confidence_weighted"],
    "default_strategy": os.getenv("DEFAULT_STRATEGY", "confidence_weighted"),
    
    # 置信度阈值
    "confidence_thresholds": {
        "low": float(os.getenv("CONFIDENCE_LOW", "0.6")),
        "medium": float(os.getenv("CONFIDENCE_MEDIUM", "0.7")),
        "high": float(os.getenv("CONFIDENCE_HIGH", "0.8")),
    },
    
    # 性能目标
    "target_throughput": 1000,  # 10 分钟 1000 份
    "target_time_minutes": 10,
}

# =============================================================================
# Web 服务配置
# =============================================================================

SERVER_CONFIG = {
    "host": os.getenv("SERVER_HOST", "0.0.0.0"),
    "port": int(os.getenv("SERVER_PORT", "5001")),
    "debug": os.getenv("FLASK_DEBUG", "false").lower() == "true",
}

# =============================================================================
# 数据库配置
# =============================================================================

DATABASE_CONFIG = {
    "url": os.getenv("DATABASE_URL", "sqlite:///data/grading.db"),
}
