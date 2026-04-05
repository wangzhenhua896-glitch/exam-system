"""
批量评分 API 路由
"""

from flask import Blueprint, request, jsonify
from loguru import logger
import time
import asyncio
from typing import List, Dict, Any

from app.engine import AggregationEngine
from config.settings import GRADING_CONFIG

batch_bp = Blueprint("batch", __name__)
engine = AggregationEngine(GRADING_CONFIG)


@batch_bp.route("/grade", methods=["POST"])
async def batch_grade():
    """批量评分"""
    try:
        data = request.get_json()
        
        items = data.get("items", [])
        rubric = data.get("rubric", {})
        max_score = float(data.get("max_score", 10))
        sample_count = int(data.get("sample_count", 3))
        strategy = data.get("strategy", "confidence_weighted")
        
        if not items:
            return jsonify({"error": "没有提供评分项"}), 400
        
        start_time = time.time()
        
        # 并行处理所有项目
        tasks = [
            engine.aggregate(
                item.get("question", ""),
                item.get("answer", ""),
                rubric,
                max_score,
                sample_count,
                strategy
            )
            for item in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # 统计
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        avg_time = elapsed / len(items) if items else 0
        
        return jsonify({
            "success": True,
            "results": [
                r.dict() if not isinstance(r, Exception) else {"error": str(r)}
                for r in results
            ],
            "stats": {
                "total": len(items),
                "success": success_count,
                "failed": len(items) - success_count,
                "elapsed": round(elapsed, 2),
                "avg_time": round(avg_time, 2),
                "throughput": round(len(items) / elapsed * 60, 1) if elapsed > 0 else 0,
            }
        })
    
    except Exception as e:
        logger.error(f"批量评分失败：{e}")
        return jsonify({"error": f"批量评分失败：{str(e)}"}), 500


@batch_bp.route("/test", methods=["POST"])
async def performance_test():
    """性能测试"""
    try:
        data = request.get_json()
        
        test_count = int(data.get("count", 100))
        rubric = data.get("rubric", {})
        max_score = float(data.get("max_score", 10))
        sample_count = int(data.get("sample_count", 3))
        strategy = data.get("strategy", "confidence_weighted")
        
        # 生成测试数据
        test_items = generate_test_items(test_count)
        
        start_time = time.time()
        
        # 批量评分
        tasks = [
            engine.aggregate(
                item.get("question", ""),
                item.get("answer", ""),
                rubric,
                max_score,
                sample_count,
                strategy
            )
            for item in test_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # 统计
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        return jsonify({
            "success": True,
            "stats": {
                "total_items": test_count,
                "success": success_count,
                "failed": test_count - success_count,
                "total_time": round(elapsed, 2),
                "avg_time_per_item": round(elapsed / test_count * 1000, 1),
                "throughput_per_minute": round(test_count / elapsed * 60, 1),
                "meets_target": (test_count / elapsed * 60) >= 100,
            }
        })
    
    except Exception as e:
        logger.error(f"性能测试失败：{e}")
        return jsonify({"error": f"性能测试失败：{str(e)}"}), 500


def generate_test_items(count: int) -> List[Dict[str, Any]]:
    """生成测试数据"""
    test_questions = [
        "请简述人工智能的发展历程。",
        "什么是机器学习？请举例说明。",
        "请解释深度学习与传统机器学习的区别。",
        "什么是神经网络？它的工作原理是什么？",
        "请简述自然语言处理的主要应用场景。",
    ]
    
    test_answers = [
        "人工智能起源于 1956 年达特茅斯会议，经历了符号主义、连接主义等发展阶段，近年来随着深度学习和大数据的兴起取得了突破性进展。",
        "机器学习是让计算机从数据中自动学习规律的技术。例如垃圾邮件过滤、推荐系统等都是机器学习的典型应用。",
        "深度学习使用多层神经网络自动学习特征表示，而传统机器学习需要人工设计特征。深度学习在图像识别、语音识别等任务上表现更优。",
        "神经网络是受生物神经系统启发的计算模型，由大量神经元节点组成。通过调整连接权重来学习输入输出之间的映射关系。",
        "自然语言处理主要应用于机器翻译、情感分析、智能客服、文本摘要等场景，近年来大语言模型取得了显著进展。",
    ]
    
    items = []
    for i in range(count):
        items.append({
            "question": test_questions[i % len(test_questions)],
            "answer": test_answers[i % len(test_answers)],
            "student_id": f"STU{i+1:04d}",
        })
    
    return items
