"""
自动调优 API 路由
"""

from flask import Blueprint, request, jsonify
from loguru import logger
import asyncio

from app.auto_tuning import AutoTuningEngine, TuningConfig, auto_tuning_engine

tuning_bp = Blueprint("tuning", __name__)


@tuning_bp.route("/start", methods=["POST"])
async def start_tuning():
    """启动自动调优"""
    try:
        data = request.get_json() or {}
        
        config = TuningConfig(
            max_iterations=int(data.get("max_iterations", 10)),
            target_accuracy=float(data.get("target_accuracy", 0.8)),
            target_correlation=float(data.get("target_correlation", 0.85)),
            max_error_threshold=float(data.get("max_error_threshold", 2.0)),
        )
        
        strategy = data.get("strategy", "confidence_weighted")
        sample_count = int(data.get("sample_count", 3))
        
        logger.info(f"开始自动调优：{config}")
        
        # 运行调优
        report = await auto_tuning_engine.tune(config, strategy, sample_count)
        
        return jsonify({
            "success": True,
            "report": report.dict(),
        })
    
    except Exception as e:
        logger.error(f"调优失败：{e}")
        return jsonify({"error": f"调优失败：{str(e)}"}), 500


@tuning_bp.route("/status", methods=["GET"])
def get_tuning_status():
    """获取调优状态"""
    return jsonify({
        "success": True,
        "status": {
            "current_temperature": auto_tuning_engine.current_temperature,
            "current_prompt_template": auto_tuning_engine.current_prompt_template,
            "best_score": auto_tuning_engine.best_score,
            "best_config": auto_tuning_engine.best_config,
        }
    })
