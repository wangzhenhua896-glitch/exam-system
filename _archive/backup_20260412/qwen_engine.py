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

from config.settings import GRADING_CONFIG
from app.models.db_models import get_effective_config


class QwenGradingResult(BaseModel):
    """评分结果"""
    final_score: Optional[float] = None
    confidence: float = 0
    strategy: str = ""
    total_score: float = 0
    comment: str = ""
    error: Optional[str] = None
    needs_review: bool = False
    warning: Optional[str] = None
    scoring_items: Optional[List[Dict[str, Any]]] = None


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
        self._selected_provider = None
        self.client, self.model, self._selected_provider = self._init_client()

    def set_provider(self, provider: str, model: str = None):
        """切换当前使用的 provider 和子模型"""
        client, mdl, prov = self._init_client(provider, model)
        if prov:
            self.client = client
            self.model = mdl
            self._selected_provider = prov
            return True
        return False

    def _init_client(self, preferred_provider: str = None, preferred_model: str = None):
        """初始化 OpenAI 兼容客户端

        优先从数据库读取配置（管理员通过 Web UI 修改后的值），
        数据库无记录时降级到 .env 默认值。

        Args:
            preferred_provider: 指定服务商
            preferred_model: 指定子模型（如 "qwen-plus"），优先于默认 model

        Returns:
            (client, model, provider) 或 (None, None, None)
        """
        import os

        # 如果指定了 provider，只尝试它
        if preferred_provider:
            cfg = get_effective_config(preferred_provider)
            if cfg.get("enabled") and cfg.get("api_key"):
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg["base_url"],
                )
                model = preferred_model or cfg["model"]
                return client, model, preferred_provider
            return None, None, None

        # 默认优先级：qwen > glm > ernie > doubao > xiaomi_mimimo
        for provider in ('qwen', 'glm', 'ernie', 'doubao', 'xiaomi_mimimo'):
            cfg = get_effective_config(provider)
            if cfg.get("enabled") and cfg.get("api_key"):
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg["base_url"],
                )
                return client, cfg["model"], provider

        # 回退到环境变量
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        client = OpenAI(api_key=api_key, base_url=base_url)
        return client, model, "openai"

    async def grade(
        self,
        question: str,
        answer: str,
        rubric: Dict[str, Any],
        max_score: float,
        subject: str = "general",
    ) -> QwenGradingResult:
        """
        对学生答案进行评分

        Args:
            question: 题目内容
            answer: 学生答案
            rubric: 评分标准（包含 points 等信息）
            max_score: 满分
            subject: 科目标识（politics/chinese/english 等），后续用于分科评分策略

        Returns:
            QwenGradingResult
        """
        try:
            # 格式化评分标准
            rubric_text = self._format_rubric(rubric, max_score)

            # 构建 Prompt（按科目走不同提示词）
            if subject == 'politics':
                system_prompt = self._get_politics_system_prompt()
            elif subject == 'chinese':
                system_prompt = self._get_chinese_system_prompt()
            elif subject == 'english':
                system_prompt = self._get_english_system_prompt()
            else:
                system_prompt = self._get_system_prompt()
            user_prompt = self._build_user_prompt(question, rubric_text, answer, max_score)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 调用 OpenAI 兼容接口（带智能重试）
            # ┌─────────────────────────────────────────────────────────────┐
            # │ 评分失败处理策略（考试场景核心原则）                          │
            # │                                                             │
            # │ 1. 绝不能静默返回0分 — 等同于误判考生成绩                     │
            # │ 2. 自动重试：最多3次，指数退避(1s/2s/4s)，避免高频加重负担    │
            # │ 3. 覆盖两类失败：API异常(网络/超时) + 解析失败(模型输出异常)  │
            # │ 4. 重试耗尽：返回 score=null，前端提示用户选择"重试"或        │
            # │    "联系监考老师人工处理"                                     │
            # │ 5. 用户手动重试：前端再次调用本接口，重新走完整重试流程        │
            # └─────────────────────────────────────────────────────────────┘
            import time
            max_retries = 3
            content = None
            parsed = None

            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.0,  # 评分需要确定性
                        max_tokens=4096,  # 足够空间容纳逐问 JSON 输出
                        stream=False,
                    )
                    content = response.choices[0].message.content.strip()
                    parsed = self._parse_output(content)

                    if not parsed.get("error"):
                        break  # 解析成功，退出重试

                    # 解析失败：模型返回了内容但无法提取分数
                    from loguru import logger
                    logger.warning(f"评分解析失败(第{attempt + 1}次): {parsed.get('error')}, 原始输出: {content[:200]}")
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt  # 指数退避：1s → 2s → 4s
                        time.sleep(wait)

                except Exception as e:
                    # 网络异常 / API 超时
                    from loguru import logger
                    logger.error(f"评分API调用异常(第{attempt + 1}次): {e}")
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt  # 指数退避：1s → 2s → 4s
                        time.sleep(wait)

            # 重试耗尽仍失败 → 返回 score=null，由前端提示用户选择重试或人工处理
            if not parsed or parsed.get("error"):
                return QwenGradingResult(
                    final_score=None,
                    confidence=0,
                    strategy="qwen_engine",
                    total_score=max_score,
                    error=parsed.get("error") if parsed else "API调用失败",
                    comment='⚠️ 评分系统暂时无法评分，请点击"重新评分"重试，如多次失败请联系监考老师人工处理',
                    needs_review=True
                )

            final_score = float(parsed.get("总分", parsed.get("score", 0)))
            comment = parsed.get("评语", parsed.get("comment", content))

            # 提取分项得分明细（总分已在 _parse_output 中由分项累加得出）
            scoring_items = parsed.get("scoring_items")
            if scoring_items and isinstance(scoring_items, list):
                validated_items = []
                for item in scoring_items:
                    if isinstance(item, dict):
                        validated_items.append({
                            "name": str(item.get("name", "")),
                            "score": float(item.get("score", 0)),
                            "max_score": float(item.get("max_score", 0)),
                            "hit": bool(item.get("hit", False)),
                            "reason": str(item.get("reason", "")),
                            "quoted_text": str(item.get("quoted_text", "")),
                        })
                scoring_items = validated_items if validated_items else None
            else:
                scoring_items = None

            # 语义相似度二次校验：发现模型漏判的等价表达并自动纠偏
            # 跳过英语科目：语义校验使用中文 text2vec 模型，不适用于英文
            semantic_warnings = []
            if scoring_items and subject != 'english':
                rubric_points = self._extract_rubric_points(rubric)
                if rubric_points:
                    try:
                        from app.semantic_checker import validate_scoring_items
                        scoring_items, sem_changes = validate_scoring_items(
                            answer, scoring_items, rubric_points,
                            similarity_threshold=0.72,
                        )
                        if sem_changes:
                            from loguru import logger
                            for ch in sem_changes:
                                logger.info(f"语义校验纠偏: {ch['item']} - {ch['action']} - {ch.get('keyword', '')}")
                            # 重新从校验后的 scoring_items 累加总分
                            final_score = round(sum(
                                float(it.get("score", 0)) for it in scoring_items
                                if isinstance(it, dict)
                            ), 2)
                            # 记录纠偏信息，后续写入 warning
                            semantic_warnings = [
                                f"要点'{ch['item']}'由语义校验自动纠偏"
                                for ch in sem_changes
                            ]
                    except Exception as e:
                        from loguru import logger
                        logger.warning(f"语义校验异常（忽略，保留模型原始评分）: {e}")

            # 计算置信度
            confidence = self._calculate_confidence(final_score, max_score, content)

            # 边界检查
            result = QwenGradingResult(
                final_score=round(final_score, 2),
                confidence=confidence,
                strategy="qwen_engine",
                total_score=max_score,
                comment=comment,
                needs_review=False,
                scoring_items=scoring_items,
                warning='；'.join(semantic_warnings) if semantic_warnings else None,
            )

            return self.boundary_check(result)

        except Exception as e:
            return QwenGradingResult(
                final_score=None,
                confidence=0,
                strategy="qwen_engine",
                total_score=max_score,
                error=str(e),
                comment='⚠️ 评分系统暂时无法评分，请点击"重新评分"重试，如多次失败请联系监考老师人工处理',
                needs_review=True
            )

    def _get_system_prompt(self) -> str:
        """获取系统提示词（参考 Qwen-Agent 设计）"""
        return """你是一位专业的阅卷老师，需要严格按照评分标准给学生答案打分。

评分流程（必须严格按此顺序执行）：
1. 先检查反作弊规则：如果评分标准中包含【反作弊规则】，必须先执行反作弊检查。
   命中反作弊条件（如复制原文、复制题干、空白、答非所问）→ 该问直接判0分，跳过逐项评分。
2. 再逐项评分：按照评分标准的评分要点逐一判断给分，每一项独立计分。
3. 不要漏判也不要错判，部分答对给部分分数。
4. 评语需要指出学生答案的优点和不足（评语不超过100字）。
5. 你必须使用 JSON 格式输出。输出格式：
{
  "评语": "你的评语",
  "scoring_items": [
    {"name": "要点名称", "score": 得分, "max_score": 该要点满分, "hit": true/false, "reason": "命中/未命中的简要原因", "quoted_text": "从学生答案中摘录的原文"}
  ]
}

注意：总分由系统根据各要点得分自动累加，你不需要输出总分，只需准确给出每个要点的得分即可。

scoring_items 规则：
- 逐条列出评分标准中的每个得分要点
- hit=true 表示学生答案命中该要点，hit=false 表示未命中或命中不完整
- score 为该要点实际得分，max_score 为该要点满分
- reason 用一句话说明为什么给这个分（不超过30字）
- quoted_text 必须是学生答案中的原文摘录，用于证明你的判断依据。hit=true 时摘录命中的关键句，hit=false 时为空字符串""。禁止编造或改写学生原文。
- 如果评分标准没有明确的分要点，则按你自己的判断拆分出要点
- 反作弊命中时，scoring_items 中所有要点 hit=false、score=0、quoted_text=""

重要：反作弊检查优先于所有评分规则。如果考生只是照抄原文/题干，即使原文中包含关键词，也必须判0分。
不要因为整体印象调整分数。对同一内容，无论学生用什么表述方式，只要语义等价，给相同分数。"""

    def _get_politics_system_prompt(self) -> str:
        """思政科目专用系统提示词"""
        return """你是一位专业的思政阅卷老师，必须严格按照评分脚本给学生答案打分。

评分流程（必须严格按此顺序执行）：
1. 先检查反作弊规则：如果评分脚本中包含【反作弊规则】或政治立场错误类判定，必须先执行检查。
   命中反作弊条件（如复制题干、复制标准答案模板、空白未作答、答非所问、政治立场错误）→ 直接判0分，跳过逐项评分。
2. 再逐项评分：严格按照评分脚本中的【逐项评分规则】逐一判断给分，每一项独立计分。
3. 分值必须完全按照评分脚本中标注的分值执行，不可自行调整或四舍五入。
4. 部分得分条件（如"得1.5分""得1分"）必须严格执行，按脚本中写的条件精确判断。
5. 等价表述按评分脚本中的等价表述表匹配。易混淆判断按脚本中的规则执行。
6. 评语需要逐个要点说明判断结果：要点1是否得分及原因，要点2是否得分及原因...（评语不超过150字）。

输出格式（严格JSON，不要输出任何其他文字）：
{
  "scoring_items": [
    {"name": "要点1：XXX", "score": 2, "max_score": 2, "hit": true, "reason": "命中关键词", "quoted_text": "学生原文摘录"},
    {"name": "要点2：XXX", "score": 0, "max_score": 2, "hit": false, "reason": "未提及", "quoted_text": ""}
  ],
  "评语": "逐个要点说明判断结果和得分情况"
}
总分由系统自动累加，你不需要输出总分。反作弊命中时所有要点 hit=false、score=0、quoted_text=""、评语说明原因。"""

    def _get_chinese_system_prompt(self) -> str:
        """语文科目专用系统提示词（古诗词鉴赏等）"""
        return """你是一位专业的语文阅卷老师，必须严格按照评分脚本给学生答案打分。

评分流程（必须严格按此顺序执行）：
1. 先检查反作弊规则：如果评分脚本中包含【反作弊规则】，必须先执行反作弊检查。
   命中反作弊条件（如复制诗歌原文、复制题干、空白未作答、答非所问）→ 该问直接判0分，跳过逐项评分。
   注意：如果考生引用了诗句后补充了自己的分析，且分析命中得分要点，应正常按要点给分。
2. 再逐项评分：严格按照评分脚本中的【逐项评分规则】逐一判断给分，每一项独立计分。
3. 分值必须完全按照评分脚本中标注的分值执行，不可自行调整。
4. 部分得分条件必须严格执行，按脚本中写的条件精确判断。
5. 等价表述按评分脚本中的等价表述表匹配。易混淆判断按脚本中的规则执行。
6. 错别字按评分脚本中的【扣分规则】执行，每处扣0.5分，扣完该问满分为止。
7. 评语需要逐个要点说明判断结果：该问是否得分、得多少分及原因。（评语不超过150字）

输出格式（严格JSON，不要输出任何其他文字）：
请忽略评分脚本中【输出格式要求】指定的格式，统一按以下 scoring_items 格式输出：
{
  "scoring_items": [
    {"name": "第1问：题材类型", "score": 2, "max_score": 2, "hit": true, "reason": "回答\"边塞诗\"", "quoted_text": "边塞诗"},
    {"name": "第2问：景物列举", "score": 3, "max_score": 4, "hit": true, "reason": "命中3种", "quoted_text": "青海、长云、雪山"},
    {"name": "错别字扣分", "score": -0.5, "max_score": 0, "hit": false, "reason": "扣0.5分", "quoted_text": ""}
  ],
  "评语": "..."
}
规则：
- 总分由系统自动累加，你不需要输出总分。
- 每个采分点（或得分条件）对应一个独立的 scoring_item。
- 错别字扣分作为独立 item，score 为负数，max_score 为 0。
- 反作弊命中时该问所有要点 hit=false、score=0、quoted_text=""。
- 只输出 JSON，不要输出任何其他文字。"""

    def _get_english_system_prompt(self) -> str:
        """英语科目专用系统提示词（阅读理解等）"""
        return """你是一位专业的英语阅卷老师，必须严格按照评分脚本给学生答案打分。

评分流程（必须严格按此顺序执行）：
1. 先检查反作弊规则：如果评分脚本中包含【反作弊规则】，必须先执行反作弊检查。
   命中反作弊条件（如复制阅读材料原文、复制题干、空白未作答、答非所问）→ 该问直接判0分，跳过逐项评分。
   注意：如果考生引用了材料原文后补充了自己的回答，且补充内容命中得分要点，应正常按要点给分。
2. 再逐项评分：严格按照评分脚本中的【逐项评分规则】逐一判断给分，每一项独立计分。
3. 分值必须完全按照评分脚本中标注的分值执行，不可自行调整。
4. 语言规则：英语题目要求用英语作答，用拼音或中文作答一律判0分。
5. 等价表述按评分脚本中的等价表述表匹配。大小写不敏感。
6. 评语需要逐个要点说明判断结果：该问是否得分、得多少分及原因。（评语不超过150字）

输出格式（严格JSON，不要输出任何其他文字）：
请忽略评分脚本中【输出格式要求】指定的格式，统一按以下 scoring_items 格式输出：
{
  "scoring_items": [
    {"name": "第1问：Spring Festival", "score": 2, "max_score": 2, "hit": true, "reason": "正确", "quoted_text": "Spring Festival"},
    {"name": "第2问：谐音寓意", "score": 1, "max_score": 2, "hit": true, "reason": "命中采分点A", "quoted_text": "surplus"},
    {"name": "第3问：烟花习俗", "score": 2, "max_score": 2, "hit": true, "reason": "全部命中", "quoted_text": "fireworks, scare away"}
  ],
  "评语": "..."
}
规则：
- 总分由系统自动累加，你不需要输出总分。
- 每个采分点（或得分条件）对应一个独立的 scoring_item。
- 反作弊命中时该问所有要点 hit=false、score=0、quoted_text=""。
- 只输出 JSON，不要输出任何其他文字。"""

    def _build_user_prompt(self, question: str, rubric: str, answer: str, max_score: float) -> str:
        """构建用户提示词"""
        import hashlib, time
        # 用答案内容+时间戳生成随机标记，打破大模型 API 的服务端缓存
        cache_buster = hashlib.md5(f"{answer}:{time.time()}".encode()).hexdigest()[:8]
        return f"""# 题目
{question}

# 满分
{max_score} 分

# 评分标准
{rubric}

# 学生答案
{answer}

请评分，并按要求输出 JSON：
<!-- req:{cache_buster} -->"""

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

    def _extract_rubric_points(self, rubric: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 rubric 字典中提取结构化的评分要点（含关键词），供语义校验使用

        返回格式: [{"description": "...", "keywords": ["kw1", "kw2"]}, ...]
        """
        points = []

        # 1. 如果 rubric 中有 points 列表（JSON 结构，含明确 keywords）
        raw_points = rubric.get("points", [])
        if raw_points and isinstance(raw_points, list):
            for p in raw_points:
                if isinstance(p, dict):
                    desc = p.get("description", "")
                    kws = p.get("keywords", [])
                    if isinstance(kws, str):
                        kws = [k.strip() for k in kws.split(",") if k.strip()]
                    if desc:
                        points.append({"description": desc, "keywords": kws or []})
                elif isinstance(p, str):
                    kws = self._keywords_from_text(p)
                    points.append({"description": p, "keywords": kws})
            if points:
                return points

        # 2. 从 rubricScript 解析 "要点N（X分）：内容" 格式（比 rubricPoints 结构更好）
        rubric_script = rubric.get("rubricScript", "")
        if rubric_script and rubric_script.strip():
            for m in re.finditer(r'要点\d+[（(]\d+分[)）][:：]\s*(.+)', rubric_script):
                desc = m.group(1).strip()
                if desc:
                    kws = self._keywords_from_text(desc)
                    points.append({"description": desc, "keywords": kws})
            if points:
                return points

        # 3. 从 rubricPoints（数据库 rubric_points 字段）解析
        rubric_points_text = rubric.get("rubricPoints", "")
        if rubric_points_text and rubric_points_text.strip():
            for line in rubric_points_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 去掉末尾的 (X分) 标记
                desc = re.sub(r'\s*[\(（]\s*\d+\s*分\s*[\)）]\s*$', '', line).strip()
                if desc:
                    kws = self._keywords_from_text(desc)
                    points.append({"description": desc, "keywords": kws})
            if points:
                return points

        return points

    @staticmethod
    def _keywords_from_text(text: str) -> List[str]:
        """从评分要点文本中提取关键词

        按顿号、逗号、"和"、"及" 等切分，过滤掉太短和太长的词。
        """
        # 去掉括号内容
        clean = re.sub(r'[（(][^)）]*[)）]', '', text)
        # 按分隔符切分
        parts = re.split(r'[、，,；;和及]', clean)
        keywords = []
        for p in parts:
            p = p.strip()
            # 只保留 2~12 字的关键词（太短如"的"无意义，太长如整句不适合作为关键词）
            if 2 <= len(p) <= 12:
                keywords.append(p)
        # 如果切分后关键词太少，把整句也加入（作为语义匹配的锚点）
        if len(keywords) < 2 and len(text) >= 4:
            keywords.append(text[:30])
        return keywords

    def _parse_output(self, content: str) -> Dict[str, Any]:
        """解析 LLM 输出

        总分始终由系统从 scoring_items 累加得出，不信任模型给出的总分。
        """
        # 尝试直接解析 JSON
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(content)

            # 优先从 scoring_items 累加总分
            scoring_items = parsed.get("scoring_items")
            if scoring_items and isinstance(scoring_items, list):
                total = 0
                for item in scoring_items:
                    if isinstance(item, dict):
                        try:
                            s = float(item.get("score", 0))
                            ms = float(item.get("max_score", 0))
                            # 分值校验：非负且不超过 max_score（错别字扣分 max_score=0 跳过上限检查）
                            if s < 0 and ms > 0:
                                s = 0
                            elif ms > 0 and s > ms:
                                s = ms
                            item["score"] = s
                            total += s
                        except (ValueError, TypeError):
                            pass
                parsed["总分"] = round(total, 2)
                return parsed

            # 兼容旧的逐问格式：{"第一问": {"得分": X}}，同时构造 scoring_items
            question_scores = []
            scoring_items = []
            for key, value in parsed.items():
                if isinstance(value, dict) and "得分" in value:
                    try:
                        score = float(value["得分"])
                        max_s = float(value.get("满分", 0))
                        comment = str(value.get("评语", ""))
                        # 分值校验：非负且不超过 max_score
                        if score < 0 and max_s > 0:
                            score = 0
                        elif max_s > 0 and score > max_s:
                            score = max_s
                        question_scores.append(score)
                        scoring_items.append({
                            "name": key,
                            "score": score,
                            "max_score": max_s,
                            "hit": score > 0,
                            "reason": comment,
                            "quoted_text": "",
                        })
                    except (ValueError, TypeError):
                        pass

            if question_scores:
                parsed["总分"] = round(sum(question_scores), 2)
                # 语文错别字扣分处理
                typo_deduction = parsed.get("错别字扣分")
                if typo_deduction is not None:
                    try:
                        typo_val = float(typo_deduction)
                        if typo_val > 0:
                            scoring_items.append({
                                "name": "错别字扣分",
                                "score": -typo_val,
                                "max_score": 0,
                                "hit": False,
                                "reason": f"扣{typo_val}分",
                                "quoted_text": "",
                            })
                    except (ValueError, TypeError):
                        pass
                if scoring_items:
                    parsed["scoring_items"] = scoring_items
                return parsed

            return parsed
        except json.JSONDecodeError:
            pass

        # 尝试正则提取分数（中英文）
        # 支持 JSON 格式键值对（如 "总分": 8）和自然语言格式（如 总分：8分）
        score_match = re.search(r'["\']?(总分|score|total)["\']?\s*[：:=\s]+\s*(\d+\.?\d*)', content)
        if score_match:
            score = float(score_match.group(2))
            return {
                "总分": score,
                "评语": content
            }

        # 英文输出兜底：匹配 "score": X 或 "total": X
        # (已合并到上方的统一正则中，此处保留兼容旧逻辑)
        score_match_en = re.search(r'"(final_score)"\s*:\s*(\d+\.?\d*)', content)
        if score_match_en:
            score = float(score_match_en.group(2))
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
        # 评分异常（final_score=None）跳过边界检查，直接返回
        if result.final_score is None:
            result.needs_review = True
            return result

        max_score = result.total_score
        warnings = []
        if result.warning:
            warnings.append(result.warning)

        if result.final_score >= max_score * 0.95:
            warnings.append("⚠️ 接近满分，建议人工复核")
            result.needs_review = True
        elif result.final_score <= max_score * 0.05:
            warnings.append("⚠️ 接近零分，建议人工复核")
            result.needs_review = True

        if result.confidence < self.confidence_thresholds["low"]:
            warnings.append("⚠️ 置信度过低，必须人工复核")
            result.needs_review = True

        result.warning = '；'.join(dict.fromkeys(warnings)) if warnings else None

        # 截断分数到合法范围
        if result.final_score < 0:
            result.final_score = 0
        elif result.final_score > max_score:
            result.final_score = max_score

        return result
