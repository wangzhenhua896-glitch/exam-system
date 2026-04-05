"""
多模型投票和聚合策略
"""

import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

from app.models.base import ModelResponse
from app.models.registry import model_registry


class GradingResult(BaseModel):
    """评分结果"""
    final_score: float
    confidence: float
    strategy: str
    model_scores: List[Dict[str, Any]] = []
    reasoning: str = ""
    needs_review: bool = False
    warning: Optional[str] = None


class AggregationEngine:
    """聚合引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.confidence_thresholds = config.get("confidence_thresholds", {
            "low": 0.6,
            "medium": 0.7,
            "high": 0.8,
        })
    
    async def aggregate(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
        sample_count: int = 3,
        strategy: str = "confidence_weighted",
    ) -> GradingResult:
        """
        聚合多模型评分结果
        
        Args:
            question: 题目
            answer: 学生答案
            rubric: 评分标准
            max_score: 满分
            sample_count: 每个模型的采样次数
            strategy: 聚合策略
            
        Returns:
            GradingResult 对象
        """
        # 获取所有启用的模型
        models = model_registry.get_enabled_models()
        
        if not models:
            return GradingResult(
                final_score=0,
                confidence=0,
                strategy=strategy,
                warning="没有可用的模型",
            )
        
        # 并行调用所有模型进行多次采样
        all_responses = await self._sample_models(
            models, question, answer, rubric, max_score, sample_count
        )
        
        # 根据策略聚合结果
        if strategy == "majority_vote":
            result = self._majority_vote(all_responses, max_score)
        elif strategy == "weighted_average":
            result = self._weighted_average(all_responses, max_score)
        elif strategy == "confidence_weighted":
            result = self._confidence_weighted(all_responses, max_score)
        else:
            result = self._confidence_weighted(all_responses, max_score)
        
        # 边界检测
        result = self._boundary_check(result, max_score)
        
        return result
    
    async def _sample_models(
        self,
        models,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
        sample_count: int,
    ) -> List[Dict[str, Any]]:
        """对每个模型进行多次采样"""
        all_responses = []
        
        for model in models:
            # 并行多次采样
            tasks = [
                model.grade_answer(question, answer, rubric, max_score)
                for _ in range(sample_count)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理响应
            for resp in responses:
                if isinstance(resp, Exception):
                    all_responses.append({
                        "model": model.model_name,
                        "provider": model.provider.value,
                        "score": 0,
                        "confidence": 0,
                        "reasoning": f"错误：{str(resp)}",
                        "error": str(resp),
                    })
                elif resp.error:
                    all_responses.append({
                        "model": model.model_name,
                        "provider": model.provider.value,
                        "score": 0,
                        "confidence": 0,
                        "reasoning": resp.error,
                        "error": resp.error,
                    })
                else:
                    all_responses.append({
                        "model": model.model_name,
                        "provider": model.provider.value,
                        "score": resp.score or 0,
                        "confidence": resp.confidence or 0.5,
                        "reasoning": resp.reasoning or "",
                    })
        
        return all_responses
    
    def _majority_vote(self, responses: List[Dict], max_score: float) -> GradingResult:
        """多数投票策略"""
        # 将分数离散化为整数
        scores = [int(round(r["score"])) for r in responses]
        
        # 统计投票
        from collections import Counter
        vote_counts = Counter(scores)
        
        # 获取最高票
        final_score = vote_counts.most_common(1)[0][0]
        final_score = float(final_score)
        
        # 计算置信度（最高票比例）
        confidence = vote_counts[round(final_score)] / len(scores) if scores else 0
        
        return GradingResult(
            final_score=final_score,
            confidence=confidence,
            strategy="majority_vote",
            model_scores=responses,
            reasoning=f"多数投票结果：{final_score} 分（{vote_counts.most_common(1)[0][1]} 票）",
        )
    
    def _weighted_average(self, responses: List[Dict], max_score: float) -> GradingResult:
        """加权平均策略"""
        if not responses:
            return GradingResult(
                final_score=0,
                confidence=0,
                strategy="weighted_average",
                model_scores=responses,
            )
        
        scores = [r["score"] for r in responses]
        final_score = float(np.mean(scores))
        confidence = float(1 - np.std(scores) / max_score) if max_score > 0 else 0
        confidence = max(0, min(confidence, 1))
        
        return GradingResult(
            final_score=round(final_score, 2),
            confidence=round(confidence, 2),
            strategy="weighted_average",
            model_scores=responses,
            reasoning=f"加权平均：{final_score:.2f} 分",
        )
    
    def _confidence_weighted(self, responses: List[Dict], max_score: float) -> GradingResult:
        """置信度加权策略（默认）"""
        if not responses:
            return GradingResult(
                final_score=0,
                confidence=0,
                strategy="confidence_weighted",
                model_scores=responses,
            )
        
        # 使用置信度作为权重
        scores = np.array([r["score"] for r in responses])
        weights = np.array([r["confidence"] for r in responses])
        
        # 过滤掉错误响应
        valid_mask = weights > 0
        if not np.any(valid_mask):
            return GradingResult(
                final_score=0,
                confidence=0,
                strategy="confidence_weighted",
                model_scores=responses,
                warning="所有模型都返回错误",
            )
        
        scores = scores[valid_mask]
        weights = weights[valid_mask]
        
        # 加权平均
        final_score = float(np.average(scores, weights=weights))
        
        # 综合置信度
        confidence = float(np.average(weights, weights=weights))
        
        # 计算一致性
        consistency = 1 - float(np.std(scores) / max_score) if max_score > 0 else 0
        consistency = max(0, min(consistency, 1))
        
        # 最终置信度是置信度和一致性的平均
        confidence = (confidence + consistency) / 2
        
        return GradingResult(
            final_score=round(final_score, 2),
            confidence=round(confidence, 2),
            strategy="confidence_weighted",
            model_scores=responses,
            reasoning=f"置信度加权：{final_score:.2f} 分，一致性：{consistency:.2f}",
        )
    
    def _boundary_check(self, result: GradingResult, max_score: float) -> GradingResult:
        """边界检测：检查极端分数"""
        # 检查满分
        if result.final_score >= max_score * 0.95:
            result.warning = "⚠️ 接近满分，建议人工复核"
            result.needs_review = True
        
        # 检查零分
        elif result.final_score <= max_score * 0.05:
            result.warning = "⚠️ 接近零分，建议人工复核"
            result.needs_review = True
        
        # 检查低置信度
        if result.confidence < self.confidence_thresholds["low"]:
            result.warning = "⚠️ 置信度过低，必须人工复核"
            result.needs_review = True
        
        return result
