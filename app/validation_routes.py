"""
评分规则验证 API 路由
"""

from flask import Blueprint, request, jsonify
from loguru import logger
import asyncio

from app.validation import ValidationEngine

validation_bp = Blueprint("validation", __name__)
engine = ValidationEngine()


@validation_bp.route("/run", methods=["POST"])
async def run_validation():
    """运行评分规则验证"""
    try:
        data = request.get_json() or {}
        
        strategy = data.get("strategy", "confidence_weighted")
        sample_count = int(data.get("sample_count", 3))
        
        logger.info(f"开始验证：strategy={strategy}, sample_count={sample_count}")
        
        # 运行验证
        report = await engine.validate(strategy, sample_count)
        
        return jsonify({
            "success": True,
            "report": report.dict(),
        })
    
    except Exception as e:
        logger.error(f"验证失败：{e}")
        return jsonify({"error": f"验证失败：{str(e)}"}), 500


@validation_bp.route("/dataset", methods=["GET"])
def get_dataset_info():
    """获取测试数据集信息"""
    from app.test_data import get_test_dataset, get_test_items
    
    dataset = get_test_dataset()
    items = get_test_items()
    
    return jsonify({
        "success": True,
        "dataset": {
            "name": dataset["name"],
            "description": dataset["description"],
            "subject": dataset["subject"],
            "max_score": dataset["max_score"],
            "question_count": len(dataset["items"]),
            "test_item_count": len(items),
        },
        "questions": [
            {
                "id": q["id"],
                "question": q["question"],
                "answer_count": len(q["student_answers"]),
            }
            for q in dataset["items"]
        ],
    })
