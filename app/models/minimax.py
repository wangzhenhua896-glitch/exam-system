"""
MiniMax 客户端
MiniMax Open API
"""

import asyncio
import json
from typing import Dict, Any, Optional
import httpx

from .base import BaseModelClient, ModelResponse, ModelProvider


class MiniMaxClient(BaseModelClient):
    """MiniMax 客户端"""
    
    provider = ModelProvider.MINIMAX
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model", "abab6.5-chat")
        self.api_key = config.get("api_key", "")
        self.group_id = config.get("group_id", "")
        self.base_url = config.get("base_url", "https://api.minimax.chat/v1")
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应"""
        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return ModelResponse(
                content=content,
                model_name=self.model_name,
                usage=usage,
            )
        except Exception as e:
            return ModelResponse(
                content="",
                model_name=self.model_name,
                error=str(e)
            )
    
    async def grade_answer(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
    ) -> ModelResponse:
        """评分学生答案"""
        prompt = self._build_grading_prompt(question, answer, rubric, max_score)
        
        response = await self.generate(
            prompt,
            temperature=0.3,
            max_tokens=1000,
        )
        
        if response.error:
            return response
        
        try:
            result = self._parse_grading_result(response.content, max_score)
            response.score = result["score"]
            response.confidence = result["confidence"]
            response.reasoning = result["reasoning"]
        except Exception as e:
            response.error = f"解析评分结果失败：{str(e)}"
        
        return response
    
    def _build_grading_prompt(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
    ) -> str:
        """构建评分提示词"""
        rubric_text = json.dumps(rubric, ensure_ascii=False, indent=2)
        
        return f"""你是一个专业的简答题评分专家。请根据评分标准对学生的答案进行评分。

## 题目
{question}

## 评分标准
{rubric_text}

## 学生答案
{answer}

## 评分要求
1. 满分：{max_score} 分
2. 请严格按照评分标准评分
3. 给出具体分数和评分理由
4. 给出你对这个评分的置信度（0-1 之间）

## 输出格式
请严格按照以下 JSON 格式输出，不要输出其他内容：
{{
    "score": <分数>,
    "confidence": <置信度 0-1>,
    "reasoning": "<评分理由>"
}}
"""
    
    def _parse_grading_result(self, content: str, max_score: float) -> Dict[str, Any]:
        """解析评分结果"""
        start = content.find("{")
        end = content.rfind("}") + 1
        
        if start == -1 or end == 0:
            raise ValueError("未找到 JSON 格式的输出")
        
        json_str = content[start:end]
        result = json.loads(json_str)
        
        score = float(result.get("score", 0))
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")
        
        score = max(0, min(score, max_score))
        confidence = max(0, min(confidence, 1))
        
        return {
            "score": score,
            "confidence": confidence,
            "reasoning": reasoning,
        }
