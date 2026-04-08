"""
基于 Qwen-Agent 评分思路的评分引擎
借鉴 Qwen 官方的 Prompt 设计和评分流程
支持所有配置的大模型使用 OpenAI 兼容接口调用
"""

import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from openai import OpenAI

from config.settings import (
    GRADING_CONFIG,
    QWEN_CONFIG,
    GLM_CONFIG,
    ERNIE_CONFIG,
    DOUBAO_CONFIG,
    XIAOMI_MIMIMO_CONFIG,
)


class QwenGradingResult(BaseModel):
    """评分结果"""
    final_score: float
    confidence: float
    strategy: str
    total_score: float
    comment: str = ""
    error: Optional[str] = None
    needs_review: bool = False
    warning: Optional[str] = None


class QwenGradingEngine:
    """基于 Qwen-Agent 评分思路的评分引擎

    借鉴 Qwen 官方的 Prompt 设计：
    1. 明确角色：你是专业阅卷老师
    2. 分点给分：按评分要点逐一判断
    3. 强制 JSON 输出：{"总分": X, "评语": "..."}
    4. 容错处理：解析失败重试，正则提取
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.confidence_thresholds = config.get("confidence_thresholds", {
            "low": 0.6,
            "medium": 0.7,
            "high": 0.8,
        })

        # 选择第一个启用的模型
        self.client, self.model = self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端，选择第一个启用的模型"""
        # 优先级：任意启用的模型都可以
        if QWEN_CONFIG.get("enabled", False) and QWEN_CONFIG.get("api_key"):
            client = OpenAI(
                api_key=QWEN_CONFIG["api_key"],
                base_url=QWEN_CONFIG["base_url"],
            )
            return client, QWEN_CONFIG["model"]
        elif GLM_CONFIG.get("enabled", False) and GLM_CONFIG.get("api_key"):
            client = OpenAI(
                api_key=GLM_CONFIG["api_key"],
                base_url=GLM_CONFIG["base_url"],
            )
            return client, GLM_CONFIG["model"]
        elif ERNIE_CONFIG.get("enabled", False) and ERNIE_CONFIG.get("api_key"):
            # 文心一言也支持 OpenAI 兼容格式
            client = OpenAI(
                api_key=ERNIE_CONFIG["api_key"],
                base_url=ERNIE_CONFIG["base_url"],
            )
            return client, ERNIE_CONFIG["model"]
        elif DOUBAO_CONFIG.get("enabled", False) and DOUBAO_CONFIG.get("api_key"):
            # 小米豆包 (字节跳动火山引擎)
            client = OpenAI(
                api_key=DOUBAO_CONFIG["api_key"],
                base_url=DOUBAO_CONFIG["base_url"],
            )
            return client, DOUBAO_CONFIG["model"]
        elif XIAOMI_MIMIMO_CONFIG.get("enabled", False) and XIAOMI_MIMIMO_CONFIG.get("api_key"):
            # 小米 Mimimo Claude 兼容端点 (OpenAI 格式)
            client = OpenAI(
                api_key=XIAOMI_MIMIMO_CONFIG["api_key"],
                base_url=XIAOMI_MIMIMO_CONFIG["base_url"],
            )
            return client, XIAOMI_MIMIMO_CONFIG["model"]
        else:
            # 回退到环境变量
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            client = OpenAI(api_key=api_key, base_url=base_url)
            return client, model

    async def grade(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
    ) -> QwenGradingResult:
        """
        对学生答案进行评分

        Args:
            question: 题目内容
            answer: 学生答案
            rubric: 评分标准（包含 points 等信息）
            max_score: 满分

        Returns:
            QwenGradingResult
        """
        try:
            # 格式化评分标准
            rubric_text = self._format_rubric(rubric, max_score)

            # 构建 Prompt（参考 Qwen-Agent 评分示例的设计）
            system_prompt = self._get_system_prompt()
            user_prompt = self._build_user_prompt(question, rubric_text, answer, max_score)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 调用 OpenAI 兼容接口
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,  # 评分需要确定性
                stream=False,
            )

            # 获取输出内容
            content = response.choices[0].message.content.strip()

            # 解析输出
            parsed = self._parse_output(content)

            if parsed.get("error"):
                return QwenGradingResult(
                    final_score=0,
                    confidence=0,
                    strategy="qwen_engine",
                    total_score=max_score,
                    error=parsed["error"],
                    comment=content,
                    needs_review=True
                )

            final_score = float(parsed.get("总分", parsed.get("score", 0)))
            comment = parsed.get("评语", parsed.get("comment", content))

            # 计算置信度
            confidence = self._calculate_confidence(final_score, max_score, content)

            # 边界检查
            result = QwenGradingResult(
                final_score=round(final_score, 2),
                confidence=confidence,
                strategy="qwen_engine",
                total_score=max_score,
                comment=comment,
                needs_review=False
            )

            return self.boundary_check(result)

        except Exception as e:
            return QwenGradingResult(
                final_score=0,
                confidence=0,
                strategy="qwen_engine",
                total_score=max_score,
                error=str(e),
                needs_review=True
            )

    def _get_system_prompt(self) -> str:
        """获取系统提示词（参考 Qwen-Agent 设计）"""
        return """你是一位专业的阅卷老师，需要严格按照评分标准给学生答案打分。

评分要求：
1. 你需要仔细阅读题目、评分标准和学生答案
2. 评分标准分为：
   - 评分规则：包含评分总则、得分规则、扣分规则、记分规则等整体要求
   - 评分要点：每个得分点的具体描述和对应分值
3. 先理解整体评分规则，再按照评分要点逐项判断给分
4. 不要漏判也不要错判，部分答对给部分分数
5. 总分不能超过满分，也不能低于 0 分
6. 最后给出总分和评语，评语需要指出学生答案的优点和不足
7. 你必须使用 JSON 格式输出，格式如下：
{
  "总分": 分数,
  "评语": "你的评语"
}

重要：严格按照评分脚本/评分标准逐项检查，每一项独立给分，最后求和。
不要因为整体印象调整分数。对同一内容，无论学生用什么表述方式，只要语义等价，给相同分数。"""

    def _build_user_prompt(self, question: str, rubric: str, answer: str, max_score: float) -> str:
        """构建用户提示词"""
        return f"""# 题目
{question}

# 满分
{max_score} 分

# 评分标准
{rubric}

# 学生答案
{answer}

请评分，并按要求输出 JSON："""

    def _format_rubric(self, rubric: Dict[str, Any], max_score: float) -> str:
        """格式化评分标准为文本
        优先使用评分脚本，如果评分脚本存在，直接使用，保证确定性和一致性
        """
        if isinstance(rubric, str):
            return rubric

        # 优先使用评分脚本（没有歧义，逻辑清晰明确，保证一致性）
        rubricScript = rubric.get("rubricScript", "")
        if rubricScript and rubricScript.strip():
            return rubricScript.strip()

        # 如果没有评分脚本，按照规则+要点方式格式化
        parts = []

        # 先输出整体评分规则
        rubricRules = rubric.get("rubricRules", "")
        if rubricRules and rubricRules.strip():
            parts.append(f"【评分规则】\n{rubricRules.strip()}")

        # 然后输出评分要点
        points = rubric.get("points", [])
        if points:
            pointLines = []
            for i, point in enumerate(points, 1):
                if isinstance(point, str):
                    desc = point
                else:
                    desc = point.get("description", "")
                if desc:
                    pointLines.append(f"{i}. {desc}")
            if pointLines:
                parts.append(f"\n【评分要点】\n{chr(10).join(pointLines)}")

        # 其他字段
        knowledge = rubric.get("knowledge", "")
        contentType = rubric.get("contentType", "")
        aiPrompt = rubric.get("aiPrompt", "")
        standardAnswer = rubric.get("standardAnswer", "")

        if knowledge:
            parts.append(f"\n知识点：{knowledge}")
        if contentType:
            parts.append(f"题型：{contentType}")
        if standardAnswer:
            parts.append(f"\n标准答案参考：\n{standardAnswer}")
        if aiPrompt:
            parts.append(f"\n评分提示：{aiPrompt}")

        if parts:
            return "\n".join(parts)

        return str(rubric)

    def _parse_output(self, content: str) -> Dict[str, Any]:
        """解析 LLM 输出"""
        # 尝试直接解析 JSON
        try:
            # 查找 JSON 块
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            # 尝试整段解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试正则提取分数
        score_match = re.search(r'(总分|得分|分数|总分是)[：:\s]*(\d+\.?\d*)', content)
        if score_match:
            score = float(score_match.group(2))
            return {
                "总分": score,
                "评语": content
            }

        # 找不到分数
        return {
            "error": "无法从输出中提取分数",
            "raw": content
        }

    def _calculate_confidence(self, score: float, max_score: float, content: str) -> float:
        """计算置信度"""
        # 分数必须在合法范围内
        if score < 0 or score > max_score:
            return 0.3

        # 如果输出包含评语且长度足够，说明输出格式正确，置信度高
        if len(content) > 100:
            return 0.85
        elif len(content) > 50:
            return 0.75
        elif len(content) > 20:
            return 0.65
        else:
            return 0.5

    def boundary_check(self, result: QwenGradingResult) -> QwenGradingResult:
        """边界检查，触发人工复核"""
        max_score = result.total_score

        if result.final_score >= max_score * 0.95:
            result.warning = "⚠️ 接近满分，建议人工复核"
            result.needs_review = True
        elif result.final_score <= max_score * 0.05:
            result.warning = "⚠️ 接近零分，建议人工复核"
            result.needs_review = True

        if result.confidence < self.confidence_thresholds["low"]:
            result.warning = "⚠️ 置信度过低，必须人工复核"
            result.needs_review = True

        # 截断分数到合法范围
        if result.final_score < 0:
            result.final_score = 0
        elif result.final_score > max_score:
            result.final_score = max_score

        return result
