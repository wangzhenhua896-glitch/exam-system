"""
自动调优引擎
自动调整评分规则直到符合预期结果
"""

import asyncio
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import numpy as np
from copy import deepcopy

from app.engine import AggregationEngine
from app.test_data import get_test_items, get_test_dataset
from app.validation import ValidationEngine, ValidationReport
from config.settings import GRADING_CONFIG


class TuningConfig(BaseModel):
    """调优配置"""
    max_iterations: int = 10  # 最大迭代次数
    target_accuracy: float = 0.8  # 目标准确率
    target_correlation: float = 0.85  # 目标相关系数
    max_error_threshold: float = 2.0  # 最大可接受误差


class TuningStep(BaseModel):
    """调优步骤"""
    iteration: int
    temperature: float
    prompt_template: str
    accuracy: float
    correlation: float
    mean_error: float
    max_error: float
    is_improved: bool
    is_target_met: bool


class TuningReport(BaseModel):
    """调优报告"""
    success: bool
    total_iterations: int
    best_iteration: int
    best_accuracy: float
    best_correlation: float
    best_mean_error: float
    best_max_error: float
    final_temperature: float
    final_prompt_template: str
    steps: List[TuningStep]
    elapsed: float
    target_met: bool


class AutoTuningEngine:
    """自动调优引擎"""
    
    def __init__(self):
        self.validation_engine = ValidationEngine()
        self.current_temperature = 0.3
        self.current_prompt_template = "default"
        self.best_config = None
        self.best_score = 0
    
    async def tune(
        self,
        config: TuningConfig = None,
        strategy: str = "confidence_weighted",
        sample_count: int = 3,
    ) -> TuningReport:
        """
        自动调优评分规则
        
        Args:
            config: 调优配置
            strategy: 聚合策略
            sample_count: 采样次数
            
        Returns:
            TuningReport 调优报告
        """
        if config is None:
            config = TuningConfig()
        
        start_time = time.time()
        steps = []
        
        # 初始验证
        print(f"🔍 开始调优...")
        print(f"📊 目标：准确率 > {config.target_accuracy*100}%, 相关系数 > {config.target_correlation}")
        
        # 迭代调优
        for iteration in range(1, config.max_iterations + 1):
            print(f"\n{'='*60}")
            print(f"🔄 迭代 {iteration}/{config.max_iterations}")
            print(f"🌡️  温度：{self.current_temperature}")
            print(f"📝 提示词模板：{self.current_prompt_template}")
            
            # 执行验证
            report = await self.validation_engine.validate(
                strategy=strategy,
                sample_count=sample_count,
            )
            
            # 计算综合得分（准确率和相关系数的加权平均）
            current_score = report.accuracy * 0.6 + report.correlation * 0.4
            
            # 检查是否达到目标
            is_target_met = (
                report.accuracy >= config.target_accuracy and
                report.correlation >= config.target_correlation
            )
            
            # 检查是否改进
            is_improved = current_score > self.best_score
            
            if is_improved:
                self.best_score = current_score
                self.best_config = {
                    "temperature": self.current_temperature,
                    "prompt_template": self.current_prompt_template,
                }
                print(f"✅ 改进！得分：{current_score:.3f}")
            else:
                print(f"❌ 未改进，得分：{current_score:.3f}")
            
            # 记录步骤
            step = TuningStep(
                iteration=iteration,
                temperature=self.current_temperature,
                prompt_template=self.current_prompt_template,
                accuracy=report.accuracy,
                correlation=report.correlation,
                mean_error=report.mean_error,
                max_error=report.max_error,
                is_improved=is_improved,
                is_target_met=is_target_met,
            )
            steps.append(step)
            
            # 检查是否达到目标
            if is_target_met:
                print(f"\n🎉 达到目标！")
                break
            
            # 调整参数
            self._adjust_parameters(iteration, report)
        
        elapsed = time.time() - start_time
        
        # 生成报告
        best_step = max(steps, key=lambda s: s.accuracy * 0.6 + s.correlation * 0.4)
        
        return TuningReport(
            success=best_step.is_target_met,
            total_iterations=len(steps),
            best_iteration=best_step.iteration,
            best_accuracy=best_step.accuracy,
            best_correlation=best_step.correlation,
            best_mean_error=best_step.mean_error,
            best_max_error=best_step.max_error,
            final_temperature=self.best_config["temperature"] if self.best_config else 0.3,
            final_prompt_template=self.best_config["prompt_template"] if self.best_config else "default",
            steps=steps,
            elapsed=round(elapsed, 2),
            target_met=best_step.is_target_met,
        )
    
    def _adjust_parameters(self, iteration: int, report: ValidationReport):
        """调整参数"""
        # 调整温度
        if report.mean_error > 3.0:
            # 误差大，降低温度使输出更稳定
            self.current_temperature = max(0.1, self.current_temperature - 0.05)
            print(f"📉 降低温度到 {self.current_temperature}")
        elif report.mean_error < 1.5 and report.correlation > 0.9:
            # 表现好，可以稍微提高温度增加多样性
            self.current_temperature = min(0.5, self.current_temperature + 0.02)
            print(f"📈 提高温度到 {self.current_temperature}")
        
        # 调整提示词模板
        if iteration % 3 == 0 and report.accuracy < 0.7:
            # 每 3 次迭代且准确率低时切换提示词
            templates = ["default", "detailed", "strict", "flexible"]
            current_idx = templates.index(self.current_prompt_template) if self.current_prompt_template in templates else 0
            next_idx = (current_idx + 1) % len(templates)
            self.current_prompt_template = templates[next_idx]
            print(f"🔄 切换提示词模板到：{self.current_prompt_template}")


# 全局实例
auto_tuning_engine = AutoTuningEngine()
