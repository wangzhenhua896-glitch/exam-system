"""
评分 API 路由
"""

from flask import Blueprint, request, jsonify
from loguru import logger
import time

from app.engine import AggregationEngine
from app.models.registry import model_registry, init_models
from config.settings import GRADING_CONFIG, QWEN_CONFIG, GLM_CONFIG, MINIMAX_CONFIG, ERNIE_CONFIG

grading_bp = Blueprint("grading", __name__)

# 初始化模型
_model_config = {
    "qwen": QWEN_CONFIG,
    "glm": GLM_CONFIG,
    "minimax": MINIMAX_CONFIG,
    "ernie": ERNIE_CONFIG,
}
init_models(_model_config)

# 创建聚合引擎
engine = AggregationEngine(GRADING_CONFIG)


@grading_bp.route("/single", methods=["POST"])
async def grade_single():
    """单题评分"""
    try:
        data = request.get_json()
        
        question = data.get("question", "")
        answer = data.get("answer", "")
        rubric = data.get("rubric", {})
        max_score = float(data.get("max_score", 10))
        sample_count = int(data.get("sample_count", 3))
        strategy = data.get("strategy", "confidence_weighted")
        
        if not question or not answer:
            return jsonify({"error": "题目和答案不能为空"}), 400
        
        start_time = time.time()
        
        # 执行评分
        result = await engine.aggregate(
            question, answer, rubric, max_score, sample_count, strategy
        )
        
        elapsed = time.time() - start_time
        
        return jsonify({
            "success": True,
            "result": result.dict(),
            "elapsed": round(elapsed, 2),
        })
    
    except Exception as e:
        logger.error(f"评分失败：{e}")
        return jsonify({"error": f"评分失败：{str(e)}"}), 500


@grading_bp.route("/models", methods=["GET"])
def list_models():
    """列出可用模型"""
    models = model_registry.list_models()
    enabled = [m for m in models if m["enabled"]]
    
    return jsonify({
        "success": True,
        "models": models,
        "enabled_count": len(enabled),
    })


@grading_bp.route("/strategies", methods=["GET"])
def list_strategies():
    """列出可用策略"""
    return jsonify({
        "success": True,
        "strategies": GRADING_CONFIG["aggregation_strategies"],
        "default": GRADING_CONFIG["default_strategy"],
    })
