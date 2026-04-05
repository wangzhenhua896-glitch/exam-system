"""
基础模型接口定义
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ModelProvider(Enum):
    """国产大模型提供商"""
    QWEN = "qwen"           # 通义千问
    GLM = "glm"             # 智谱 GLM
    MINIMAX = "minimax"     # MiniMax
    ERNIE = "ernie"         # 百度文心
    SPARK = "spark"         # 讯飞星火


class ModelResponse(BaseModel):
    """模型响应"""
    content: str
    score: Optional[float] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    model_name: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class BaseModelClient(ABC):
    """基础模型客户端"""
    
    provider: ModelProvider
    model_name: str
    enabled: bool = True
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """
        生成响应
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            ModelResponse 对象
        """
        pass
    
    @abstractmethod
    async def grade_answer(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
    ) -> ModelResponse:
        """
        评分学生答案
        
        Args:
            question: 题目
            answer: 学生答案
            rubric: 评分标准
            max_score: 满分
            
        Returns:
            ModelResponse 包含分数和置信度
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "enabled": self.enabled,
        }
