"""
评分规则验证引擎
使用测试数据验证评分规则的合理性
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

from app.engine import AggregationEngine
from app.test_data import get_test_items, get_test_dataset
from config.settings import GRADING_CONFIG


class ItemResult(BaseModel):
    """单项评分结果"""
    question_id: int
    question: str
    student_answer: str
    expected_score: float
    actual_score: float
    confidence: float
    description: str
    error: float  # 误差
    is_acceptable: bool  # 是否可接受（误差在阈值内）


class ValidationReport(BaseModel):
    """验证报告"""
    total_items: int
    success_count: int
    failed_count: int
    accuracy: float  # 准确率（可接受的比例）
    mean_error: float  # 平均误差
    std_error: float  # 误差标准差
    max_error: float  # 最大误差
    correlation: float  # 与预期分数的相关系数
    item_results: List[ItemResult]
    elapsed: float
    strategy: str
    sample_count: int


class ValidationEngine:
    """评分规则验证引擎"""
    
    def __init__(self):
        self.engine = AggregationEngine(GRADING_CONFIG)
    
    async def validate(
        self,
        strategy: str = "confidence_weighted",
        sample_count: int = 3,
    ) -> ValidationReport:
        """
        验证评分规则
        
        Args:
            strategy: 聚合策略
            sample_count: 采样次数
            
        Returns:
            ValidationReport 验证报告
        """
        test_items = get_test_items()
        dataset = get_test_dataset()
        max_score = dataset["max_score"]
        
        start_time = time.time()
        
        # 并行评分
        tasks = [
            self._grade_item(item, max_score, sample_count, strategy)
            for item in test_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # 处理结果
        item_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                item_results.append(ItemResult(
                    question_id=test_items[i]["question_id"],
                    question=test_items[i]["question"],
                    student_answer=test_items[i]["student_answer"],
                    expected_score=test_items[i]["expected_score"],
                    actual_score=0,
                    confidence=0,
                    description=test_items[i]["description"],
                    error=test_items[i]["expected_score"],
                    is_acceptable=False,
                ))
            else:
                item_results.append(result)
        
        # 计算统计指标
        errors = [r.error for r in item_results]
        expected_scores = [r.expected_score for r in item_results]
        actual_scores = [r.actual_score for r in item_results]
        
        # 计算相关系数
        if len(expected_scores) > 1 and len(actual_scores) > 1:
            correlation = float(np.corrcoef(expected_scores, actual_scores)[0, 1])
            if np.isnan(correlation):
                correlation = 0
        else:
            correlation = 0
        
        # 可接受标准：误差 <= 2 分
        acceptable_threshold = 2.0
        success_count = sum(1 for e in errors if e <= acceptable_threshold)
        
        return ValidationReport(
            total_items=len(item_results),
            success_count=success_count,
            failed_count=len(item_results) - success_count,
            accuracy=success_count / len(item_results) if item_results else 0,
            mean_error=float(np.mean(errors)),
            std_error=float(np.std(errors)),
            max_error=float(max(errors)),
            correlation=correlation,
            item_results=item_results,
            elapsed=round(elapsed, 2),
            strategy=strategy,
            sample_count=sample_count,
        )
    
    async def _grade_item(
        self,
        item: Dict[str, Any],
        max_score: float,
        sample_count: int,
        strategy: str,
    ) -> ItemResult:
        """评分单个项目"""
        result = await self.engine.aggregate(
            question=item["question"],
            answer=item["student_answer"],
            rubric={},
            max_score=max_score,
            sample_count=sample_count,
            strategy=strategy,
        )
        
        actual_score = result.final_score
        expected_score = item["expected_score"]
        error = abs(actual_score - expected_score)
        
        return ItemResult(
            question_id=item["question_id"],
            question=item["question"],
            student_answer=item["student_answer"],
            expected_score=expected_score,
            actual_score=round(actual_score, 2),
            confidence=round(result.confidence, 2),
            description=item["description"],
            error=round(error, 2),
            is_acceptable=error <= 2.0,
        )
