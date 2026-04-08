"""
基础模型接口定义
"""

import json
import re
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
    DOUBAO = "doubao"       # 字节跳动豆包（火山引擎）


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
        prompt = self._build_grading_prompt(question, answer, rubric, max_score)

        response = await self.generate(
            prompt,
            temperature=0.0,  # 温度0保证最大一致性
            max_tokens=1000,
        )

        if response.error:
            return response

        # 解析评分结果
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
        """
        构建评分提示词（共用逻辑）
        支持：单个标准答案、多个标准答案、得分点拆分
        """
        rubric_text = json.dumps(rubric, ensure_ascii=False, indent=2)

        # 如果有标准答案，加入提示词 - 支持单个或多个标准答案
        standard_answer = rubric.get("standard_answer", "")
        standard_answers = rubric.get("standard_answers", [])
        scoring_points = rubric.get("scoring_points", [])
        scoring_points_text = ""
        if scoring_points:
            scoring_points_text = "## 得分点\n"
            for i, point in enumerate(scoring_points, 1):
                scoring_points_text += f"{i}. {point['content']} ({point['points']}分)\n"

        prompt = f"""你是一个专业的简答题评分专家。请严格按照评分标准对学生的答案进行评分。

## 题目
{question}

"""
        # 处理多个标准答案
        if standard_answers and isinstance(standard_answers, list) and len(standard_answers) > 0:
            prompt += "## 标准答案（多个等价答案都接受）\n"
            for i, ans in enumerate(standard_answers, 1):
                prompt += f"{i}. {ans}\n"
            prompt += "\n注意：学生答案只要与任一标准答案意思一致即可给分\n\n"
        elif standard_answer:
            prompt += f"""## 标准答案
{standard_answer}

"""

        if scoring_points_text:
            prompt += scoring_points_text + "\n"

        if rubric_text and not standard_answer and not standard_answers:
            prompt += f"""## 评分标准
{rubric_text}

"""

        prompt += f"""## 学生答案
{answer}

## 评分要求
1. 满分：{max_score} 分
2. **逐个得分点检查**：每个得分点判断学生答案是否涵盖该要点
3. **部分得分原则**：如果学生只答对了得分点的一部分，应该给部分分数，不要直接给零分
4. **语义宽容原则**：只要学生答案的意思与得分点或标准答案相近，就应该给分，不要抠字眼
5. **多答案接受原则**：如果题目允许多个标准答案，学生答案匹配其中任意一个都是正确的
6. **一致性原则**：相同意思的答案应该给出相同分数，不同程度的答案对应不同分数
7. 扣分要有依据，不随意扣分
8. 最后给出总分和评分理由
9. 给出你对这个评分的置信度（0-1 之间）：如果学生答案清晰、符合要点，置信度高；如果模糊不清存在歧义，置信度低

## 输出格式
请严格按照以下 JSON 格式输出，不要输出其他内容：
{{
    "score": <分数，保留1位小数>,
    "confidence": <置信度 0-1>,
    "reasoning": "<评分理由，逐点说明>"
}}
"""
        return prompt

    def _parse_grading_result(self, content: str, max_score: float) -> Dict[str, Any]:
        """
        解析评分结果，支持多种不规范格式（共用逻辑）
        """
        # 尝试多次提取 JSON
        result = None

        # 方法1：提取第一个 { 到最后一个 }
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > 0:
            try:
                json_str = content[start:end]
                result = json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 方法2：如果失败，尝试找第一个 { 到第一个 }（有些模型会在JSON后加说明）
        if result is None and start != -1:
            try:
                end_first = content.find("}", start) + 1
                if end_first > start:
                    json_str = content[start:end_first]
                    result = json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 方法3：正则提取分数和置信度（应对不输出JSON的情况）
        if result is None:
            # 尝试用正则提取
            score_match = re.search(r'"score"\s*:\s*([\d\.]+)', content)
            conf_match = re.search(r'"confidence"\s*:\s*([\d\.]+)', content)

            if score_match:
                score = float(score_match.group(1))
                confidence = float(conf_match.group(1)) if conf_match else 0.5
                reasoning = content
                result = {"score": score, "confidence": confidence, "reasoning": reasoning}
            else:
                raise ValueError(f"无法解析评分结果: {content[:200]}...")

        score = float(result.get("score", 0))
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", content)

        # 验证分数范围
        score = max(0, min(score, max_score))
        confidence = max(0, min(confidence, 1))

        return {
            "score": score,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    def get_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "enabled": self.enabled,
        }
