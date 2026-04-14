"""
英语科目评分独立模块

包含：
- 文本标准化、中文/拼音检测
- 采分点精确匹配（max_hit_score / hit_count）
- LLM 兜底评分
- 英语评分主流程 grade_english()

外部调用入口：
  from app.english_grader import grade_english
"""

import asyncio
import hashlib
import json
import re
import string
import time
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger


# ============================================================
# 文本处理工具
# ============================================================

def normalize_english_text(text: str) -> str:
    """
    英文文本标准化流水线：
    original → lowercase → remove punctuation (keep spaces and apostrophes)
    → remove leading articles (a/an/the) → collapse whitespace
    """
    if not text:
        return ''
    text = text.lower()
    # 保留撇号(apostrophe)，移除其他标点
    punct_to_remove = string.punctuation.replace("'", '')
    text = text.translate(str.maketrans('', '', punct_to_remove))
    # 移除开头的冠词 a/an/the
    text = re.sub(r'^(a|an|the)\s+', '', text)
    # 合并连续空格
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_cjk(text: str) -> bool:
    """检测是否包含中文/日文汉字字符"""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def detect_pinyin(text: str, whitelist: List[str] = None) -> bool:
    """
    拼音检测（保守策略：不确定时返回 False，交给 LLM 处理）

    流程：先移除白名单词汇 → 再检测典型拼音声母+韵母组合
    """
    if not text or not text.strip():
        return False

    cleaned = text
    # 移除白名单词汇（不区分大小写）
    if whitelist:
        for word in whitelist:
            cleaned = re.sub(re.escape(word), '', cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()
    if not cleaned:
        return False

    # 如果包含中文字符，不是纯拼音，返回 False
    if detect_cjk(cleaned):
        return False

    # 只检查全字母的文本（移除空格和数字后）
    alpha_only = re.sub(r'[\s\d]', '', cleaned)
    if not alpha_only or not alpha_only.isalpha():
        return False

    # 典型拼音声母：zh/ch/sh 是拼音特有；q/x/j 在英语中极少作单词起始
    initial_patterns = r'^(zh|ch|sh|q|x|j)'
    # 典型拼音韵母：去掉英语常见的 in/ing/en/un/on，只保留纯拼音特征韵母
    final_patterns = r'(ang|eng|ong|ao|ou|iu|ie|ue|ai|ei|ui|uo|ia|ua|an)$'

    words = cleaned.split()
    pinyin_word_count = 0
    for word in words:
        if len(word) < 2 or len(word) > 8:
            continue
        has_initial = bool(re.search(initial_patterns, word))
        has_final = bool(re.search(final_patterns, word))
        if has_initial and has_final:
            pinyin_word_count += 1

    # 如果超过一半的词匹配拼音模式，判定为拼音
    if words and pinyin_word_count > len(words) / 2:
        return True

    return False


# ============================================================
# 采分点匹配
# ============================================================

def _word_boundary_match(phrase: str, normalized_answer: str) -> bool:
    """用单词边界匹配，避免 compass 匹配到 compassion"""
    normalized_phrase = normalize_english_text(phrase)
    if not normalized_phrase:
        return False
    # 多词短语：每个词都用 \b 包裹，词之间用 \s+ 连接
    words = normalized_phrase.split()
    pattern = r'\b' + r'\s+'.join(re.escape(w) for w in words) + r'\b'
    return bool(re.search(pattern, normalized_answer))


def _match_scoring_point(sp: Dict, normalized_answer: str) -> Tuple[bool, str, str]:
    """
    检查单个采分点是否命中

    Returns:
        (matched: bool, matched_phrase: str, match_type: str)
        match_type: 'keyword' | 'synonym' | ''
    """
    keywords = sp.get('keywords', [])
    for phrase in keywords:
        if _word_boundary_match(phrase, normalized_answer):
            return True, phrase, 'keyword'

    synonyms = sp.get('synonyms', [])
    for phrase in synonyms:
        if _word_boundary_match(phrase, normalized_answer):
            return True, phrase, 'synonym'

    return False, '', ''


def english_scoring_point_match(answer: str, scoring_point_json: Dict, max_score: float) -> Tuple[float, Dict]:
    """
    英语采分点匹配主函数

    Args:
        answer: 学生答案文本
        scoring_point_json: 单个子题的采分点结构化 JSON，格式见文档
        max_score: 满分值

    Returns:
        (score, detail_dict)
    """
    # 1. 标准化学生答案
    normalized_answer = normalize_english_text(answer)

    sub_question_id = scoring_point_json.get('id', '')
    pinyin_whitelist = scoring_point_json.get('pinyin_whitelist', [])

    # 2. 预检
    if detect_cjk(answer):
        return 0.0, {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'reason': 'cjk_detected',
            'hit_items': [],
            'comment': '检测到中文字符，跳过采分点匹配，得0分。',
            'scoring_items': [],
        }

    word_count = len(normalized_answer.split()) if normalized_answer else 0
    if word_count < 1:
        return 0.0, {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'reason': 'too_short',
            'hit_items': [],
            'comment': '答案为空，得0分。',
            'scoring_items': [],
        }

    if detect_pinyin(answer, whitelist=pinyin_whitelist):
        return 0.0, {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'reason': 'pinyin_detected',
            'hit_items': [],
            'comment': '检测到拼音内容，跳过采分点匹配，得0分。',
            'scoring_items': [],
        }

    # 3. 排除词表检查
    exclude_list = scoring_point_json.get('exclude_list', [])
    for exclude_phrase in exclude_list:
        normalized_exclude = normalize_english_text(exclude_phrase)
        if normalized_exclude and _word_boundary_match(exclude_phrase, normalized_answer):
            return 0.0, {
                'method': 'english_scoring_point',
                'sub_question_id': sub_question_id,
                'reason': 'exclude_list_hit',
                'hit_items': [],
                'comment': f'命中排除词"{exclude_phrase}"，得0分。',
                'scoring_items': [],
            }

    # 4. 评分公式处理
    scoring_points = scoring_point_json.get('scoring_points', [])
    score_formula = scoring_point_json.get('score_formula', 'max_hit_score')
    hit_items = []
    scoring_items = []

    if score_formula == 'max_hit_score':
        # 遍历所有采分点，构建 scoring_items，找到最高分的命中
        best_hit = None  # (sp_id, score, matched_phrase, match_type, keywords_display)
        for sp in scoring_points:
            sp_id = sp.get('id', '')
            sp_score = sp.get('score', 0)
            keywords = sp.get('keywords', [])
            matched, matched_phrase, match_type = _match_scoring_point(sp, normalized_answer)

            kw_display = ', '.join(keywords) if keywords else ''
            item_name = f'采分点{sp_id}: {kw_display}' if kw_display else f'采分点{sp_id}'
            if matched:
                type_label = '关键词' if match_type == 'keyword' else '同义词'
                reason = f'命中{type_label}"{matched_phrase}"'
                matched_display = f'{matched_phrase} ({type_label})'
            else:
                reason = '未命中'
                matched_display = ''
            scoring_items.append({
                'name': item_name,
                'score': sp_score if matched else 0,
                'max_score': sp_score,
                'hit': matched,
                'reason': reason,
                'matched_by': matched_display,
            })

            if matched:
                if best_hit is None or sp_score > best_hit[1]:
                    best_hit = (sp_id, sp_score, matched_phrase, match_type, kw_display)

        if best_hit is not None:
            sp_id, sp_score, matched_phrase, match_type, kw_display = best_hit
            type_label = '关键词' if match_type == 'keyword' else '同义词'
            hit_items.append({
                'id': sp_id,
                'score': sp_score,
                'keywords_matched': [f'{matched_phrase} ({type_label})'],
            })
            comment = f'命中采分点{sp_id} ({kw_display})，{type_label}匹配"{matched_phrase}"，得{sp_score}分。'
            return sp_score, {
                'method': 'english_scoring_point',
                'sub_question_id': sub_question_id,
                'hit_items': hit_items,
                'comment': comment,
                'scoring_items': scoring_items,
            }

        # 未命中任何采分点
        return 0.0, {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'hit_items': [],
            'comment': '未命中任何采分点，得0分。',
            'scoring_items': scoring_items,
        }

    elif isinstance(score_formula, dict) and score_formula.get('type') == 'hit_count':
        # 命中计数模式：检查所有采分点，统计命中数，按 rules 查得分
        for sp in scoring_points:
            sp_id = sp.get('id', '')
            keywords = sp.get('keywords', [])
            matched, matched_phrase, match_type = _match_scoring_point(sp, normalized_answer)

            kw_display = ', '.join(keywords) if keywords else ''
            item_name = f'采分点{sp_id}: {kw_display}' if kw_display else f'采分点{sp_id}'
            if matched:
                type_label = '关键词' if match_type == 'keyword' else '同义词'
                reason = f'命中{type_label}"{matched_phrase}"'
                matched_display = f'{matched_phrase} ({type_label})'
            else:
                reason = '未命中'
                matched_display = ''
            scoring_items.append({
                'name': item_name,
                'score': sp.get('score', 1) if matched else 0,
                'max_score': sp.get('score', 1),
                'hit': matched,
                'reason': reason,
                'matched_by': matched_display,
            })

            if matched:
                hit_items.append({
                    'id': sp_id,
                    'score': 0,
                    'keywords_matched': [f'{matched_phrase} ({type_label})'],
                })

        total_hits = len(hit_items)
        rules = score_formula.get('rules', [])
        # 按 min_hits 降序排列，匹配第一条满足的规则
        sorted_rules = sorted(rules, key=lambda r: r.get('min_hits', 0), reverse=True)

        final_score = 0
        for rule in sorted_rules:
            if total_hits >= rule.get('min_hits', 0):
                final_score = rule.get('score', 0)
                break

        if final_score > 0:
            comment = f'命中{total_hits}个采分点，得{final_score}分。'
        else:
            comment = '未命中任何采分点，得0分。'

        return float(final_score), {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'hit_items': hit_items,
            'total_hits': total_hits,
            'comment': comment,
            'scoring_items': scoring_items,
        }

    else:
        # 未知公式类型，返回 0
        logger.warning(f"未知的 score_formula 类型: {score_formula}")
        return 0.0, {
            'method': 'english_scoring_point',
            'sub_question_id': sub_question_id,
            'reason': 'unknown_score_formula',
            'hit_items': [],
            'comment': f'未知评分公式类型，得0分。',
            'scoring_items': [],
        }


# ============================================================
# LLM 兜底评分
# ============================================================

def format_scoring_points_for_prompt(sp_json: Dict) -> str:
    """将采分点 JSON 格式化为 LLM prompt 文本"""
    lines = []
    for sp in sp_json.get('scoring_points', []):
        kw = ', '.join(sp.get('keywords', []))
        syn = ', '.join(sp.get('synonyms', []))
        line = f"- {sp['id']}（{sp['score']}分）: {kw}"
        if syn:
            line += f" | 同义表达: {syn}"
        lines.append(line)

    formula = sp_json.get('score_formula')
    if isinstance(formula, str) and formula == 'max_hit_score':
        lines.append("计分方式：取命中采分点中的最高分。")
    elif isinstance(formula, dict) and formula.get('type') == 'hit_count':
        rules = formula.get('rules', [])
        rules_text = '，'.join(f"命中{r['min_hits']}个→{r['score']}分" for r in rules)
        lines.append(f"计分方式：统计命中数，按规则计分：{rules_text}")

    return '\n'.join(lines)


def _get_english_fallback_system_prompt() -> str:
    """英语 LLM 兜底系统提示词

    精确匹配未命中时，用采分点 JSON 让 LLM 判断语义等价。
    采分点是唯一评分依据，LLM 不能创造采分点之外的给分理由。
    """
    return """你是一位专业的英语考试阅卷老师。你的任务是判断学生的英语答案是否语义上匹配任何采分点。

规则：
1. 将学生的答案与每个采分点的关键词和同义词进行对比。匹配是指学生答案表达了相同的意思，即使用词不同。
2. 如果答案语义上匹配某个采分点，给该采分点的分值。
3. 如果答案意思正确但不匹配任何采分点，给0分。采分点是唯一的评分依据。
4. 如果答案跑题、用中文或拼音作答，给0分。
5. 额外的正确信息不扣分。
6. 对同义表达要宽容——学生可能用不同的说法表达。

【重要】所有输出内容必须使用中文，包括评语、评分理由、评分项名称等，禁止使用英文输出。
例如：reason 应写"语义匹配'spring festival'"，不要写"Semantically matches..."。
comment 应用中文写评语，不要用英文。

输出格式（严格JSON，不要其他内容）：
{
  "scoring_items": [
    {"name": "采分点A: [关键词]", "score": 2, "max_score": 2, "hit": true, "reason": "语义匹配[关键词]", "quoted_text": "学生答案中的相关文字"}
  ],
  "comment": "简要评分说明（100字以内，用中文写）"
}
- 总分由系统计算，不要输出总分。
- 每个采分点对应一个 scoring_item。
- 所有输出内容（comment、reason、name）使用中文，禁止使用英文。
- 只输出JSON，不要其他内容。"""


def grade_english_fallback(
    client,
    model: str,
    question: str,
    answer: str,
    scoring_point_json: Dict[str, Any],
    max_score: float,
) -> Optional[Any]:
    """英语 LLM 兜底评分

    Args:
        client: OpenAI 兼容客户端
        model: 模型名称
        question: 题目内容
        answer: 学生答案
        scoring_point_json: 采分点 JSON
        max_score: 满分值

    Returns:
        QwenGradingResult 或 None
    """
    from app.qwen_engine import QwenGradingResult

    try:
        system_prompt = _get_english_fallback_system_prompt()

        sp_text = format_scoring_points_for_prompt(scoring_point_json)
        exclude_list = scoring_point_json.get('exclude_list', [])

        cache_buster = hashlib.md5(f"{answer}:{time.time()}".encode()).hexdigest()[:8]

        user_prompt = f"""# 题目
{question}

# 满分
{max_score} 分

# 采分点
{sp_text}

# 排除词表（命中则0分）
{', '.join(exclude_list) if exclude_list else '无'}

# 学生答案
{answer}

请判断学生答案是否语义匹配任何采分点，按要求输出JSON（所有内容用中文）：
<!-- req:{cache_buster} -->"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        max_retries = 3
        content = None
        parsed = None

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=4096,
                    stream=False,
                )
                content = response.choices[0].message.content.strip()
                parsed = _parse_english_output(content)

                if not parsed.get("error"):
                    break

                logger.warning(f"英语兜底解析失败(第{attempt + 1}次): {parsed.get('error')}, 原始: {content[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"英语兜底API异常(第{attempt + 1}次): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        if not parsed or parsed.get("error"):
            return QwenGradingResult(
                final_score=None,
                confidence=0,
                strategy="english_fallback",
                total_score=max_score,
                error=parsed.get("error") if parsed else "API调用失败",
                comment='⚠️ 评分系统暂时无法评分，请点击"重新评分"重试',
                needs_review=True
            )

        final_score = float(parsed.get("总分", parsed.get("score", 0)))
        comment = parsed.get("评语", parsed.get("comment", content))

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

        confidence = _calculate_confidence(final_score, max_score, content)

        result = QwenGradingResult(
            final_score=round(final_score, 2),
            confidence=confidence,
            strategy="english_fallback",
            total_score=max_score,
            comment=comment,
            needs_review=False,
            scoring_items=scoring_items,
        )

        # 边界检查
        if final_score > max_score:
            result.final_score = max_score
            result.warning = f"得分({final_score})超过满分({max_score})，已自动修正"
        elif final_score < 0:
            result.final_score = 0
            result.warning = f"得分({final_score})为负数，已自动修正"

        return result

    except Exception as e:
        return QwenGradingResult(
            final_score=None,
            confidence=0,
            strategy="english_fallback",
            total_score=max_score,
            error=str(e),
            comment='⚠️ 评分系统暂时无法评分，请点击"重新评分"重试',
            needs_review=True
        )


def _parse_english_output(content: str) -> Dict[str, Any]:
    """解析英语 LLM 输出"""
    try:
        # 尝试直接解析 JSON
        # 先清理可能的 markdown 代码块
        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        parsed = json.loads(cleaned)
        return parsed
    except json.JSONDecodeError:
        # 正则提取
        pass

    # 尝试从文本中提取 JSON
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # 尝试提取分数
    score_match = re.search(r'"(?:总分|score|final_score)"\s*:\s*(\d+(?:\.\d+)?)', content)
    if score_match:
        return {"score": float(score_match.group(1)), "评语": content[:200]}

    return {"error": "无法解析评分结果", "raw": content[:200]}


def _calculate_confidence(score: float, max_score: float, content: str) -> float:
    """计算置信度"""
    if score is None:
        return 0.0
    ratio = score / max_score if max_score > 0 else 0
    # 基础置信度
    confidence = 0.7 + 0.2 * ratio
    # 如果内容包含详细评分过程，提升置信度
    if 'scoring_items' in content or '得分' in content:
        confidence += 0.1
    return min(round(confidence, 2), 0.95)


# ============================================================
# 英语评分主流程
# ============================================================

def grade_english(
    answer: str,
    question_answers: List[Dict],
    max_score: float,
    grading_engine,
    question: str = '',
    rubric: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    英语科目评分主流程 — 逐子题独立评分

    流程：
    1. 从 question_answers 中提取所有子题的采分点 JSON
    2. 对每个子题独立执行精确匹配
    3. 如果所有子题都精确命中 → 直接返回，跳过 LLM
    4. 如果任一子题未命中 → 该子题走 LLM 兜底
    5. 总分 = 各子题得分之和

    Returns:
        {
            'final_score': float,
            'strategy': 'max',
            'layer_scores': {'keyword': float, 'vector': None, 'llm': float|None},
            'layer_details': {'keyword': {...}, 'vector': {...}, 'llm': {...}},
            'llm_result': QwenGradingResult | None,
        }
    """
    layer_scores = {'keyword': None, 'vector': None, 'llm': None}
    layer_details = {'keyword': {}, 'vector': {}, 'llm': {}}

    # 英语跳过向量层
    layer_details['vector'] = {'reason': '英语科目跳过向量匹配'}

    # 提取所有子题采分点
    scoring_point_rows = [
        a for a in question_answers
        if a.get('scope_type') == 'scoring_point'
    ]

    if not scoring_point_rows:
        # 无采分点数据，回退通用评分
        layer_details['keyword'] = {'reason': '无采分点数据'}
        logger.info("英语评分: 无采分点数据，回退通用评分")
        try:
            llm_result = grading_engine.grade(
                question=question,
                answer=answer,
                rubric=rubric or {},
                max_score=max_score,
                subject='english',
            )
        except Exception as e:
            logger.warning(f"英语通用评分异常: {e}")
            llm_result = None

        layer_scores['llm'] = llm_result.final_score if llm_result else None
        layer_details['llm'] = llm_result.dict() if llm_result else {'error': 'LLM评分失败'}
        from app.three_layer_grader import _apply_strategy
        final_score = _apply_strategy(layer_scores, 'max')
        return {
            'final_score': final_score,
            'strategy': 'max',
            'layer_scores': layer_scores,
            'layer_details': layer_details,
            'llm_result': llm_result,
        }

    # ===== 逐子题评分 =====
    total_keyword_score = 0.0
    total_llm_score = 0.0
    all_scoring_items = []      # 合并到前端展示
    all_keyword_details = []    # 按子题记录
    all_llm_details = []
    all_llm_results = []
    has_any_miss = False

    for sp_row in scoring_point_rows:
        try:
            sp_json = json.loads(sp_row.get('answer_text', '{}'))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"采分点JSON解析失败: {e}")
            continue

        sub_id = sp_json.get('id', '')
        sub_max = sp_json.get('max_score', max_score)

        _debug = logger.level == 'DEBUG'
        if _debug:
            logger.debug(f"[英语评分] 子题{sub_id}: max_score={sub_max}, points={len(sp_json.get('scoring_points', []))}个")

        # 精确匹配
        kw_score, kw_detail = english_scoring_point_match(answer, sp_json, sub_max)

        # 添加子题标识到 scoring_items
        sub_items = kw_detail.get('scoring_items', [])
        for item in sub_items:
            item['sub_question'] = sub_id

        if kw_score is not None and kw_score >= sub_max:
            # 该子题满分，精确命中
            total_keyword_score += kw_score
            all_keyword_details.append({'sub_question': sub_id, **kw_detail})
            all_scoring_items.extend(sub_items)
            logger.info(f"英语子题{sub_id}精确命中: {kw_score}/{sub_max}")
        else:
            # 该子题未满分或零分，走 LLM 兜底
            has_any_miss = True
            total_keyword_score += kw_score if kw_score else 0
            all_keyword_details.append({'sub_question': sub_id, **kw_detail})

            # LLM 兜底
            llm_sub_result = None
            try:
                if hasattr(grading_engine, 'client') and sp_json.get('scoring_points'):
                    llm_sub_result = grade_english_fallback(
                        client=grading_engine.client,
                        model=grading_engine.model,
                        question=question,
                        answer=answer,
                        scoring_point_json=sp_json,
                        max_score=sub_max,
                    )
            except Exception as e:
                logger.warning(f"英语子题{sub_id}LLM兜底异常: {e}")

            if llm_sub_result and llm_sub_result.final_score is not None:
                # 取精确匹配和 LLM 兜底的最高分（对学生有利）
                best_score = max(kw_score or 0, llm_sub_result.final_score)
                total_llm_score += llm_sub_result.final_score

                # 用得分更高的来源的 scoring_items
                if llm_sub_result.final_score > (kw_score or 0) and llm_sub_result.scoring_items:
                    llm_items = llm_sub_result.scoring_items
                    for item in llm_items:
                        item['sub_question'] = sub_id
                    all_scoring_items.extend(llm_items)
                else:
                    all_scoring_items.extend(sub_items)

                all_llm_results.append(llm_sub_result)
                all_llm_details.append({
                    'sub_question': sub_id,
                    'final_score': llm_sub_result.final_score,
                    'comment': llm_sub_result.comment,
                })
                logger.info(f"英语子题{sub_id} LLM兜底: 精确={kw_score}, LLM={llm_sub_result.final_score}, 取最优={best_score}")
            else:
                # LLM 也失败，保留精确匹配结果
                all_scoring_items.extend(sub_items)
                total_llm_score += 0
                all_llm_details.append({'sub_question': sub_id, 'error': 'LLM评分失败'})

    # 总分 = 精确匹配总分（未命中子题取 LLM 最高分已在上面累加）
    # 最终得分：取各子题最优得分之和
    final_keyword = round(total_keyword_score, 2)

    # 汇总评语
    if not has_any_miss:
        comment = f'全部{len(scoring_point_rows)}个子题精确匹配命中，共得{final_keyword}分。'
    else:
        # 收集各子题评语
        sub_comments = []
        for detail in all_keyword_details:
            sub_id = detail.get('sub_question', '')
            sub_comment = detail.get('comment', '')
            if sub_comment:
                sub_comments.append(f'{sub_id}: {sub_comment}')
        # 追加 LLM 评语
        for llm_d in all_llm_details:
            if llm_d.get('comment'):
                sub_comments.append(f'{llm_d["sub_question"]}(AI): {llm_d["comment"]}')
        comment = '\n'.join(sub_comments) if sub_comments else f'评分完成，共得{final_keyword}分。'

    # 构造合并的 llm_result（供 api_routes 使用）
    combined_llm_result = None
    if all_llm_results:
        # 取最后一个有效的 LLM 结果作为基础，但用合并数据覆盖
        combined_llm_result = all_llm_results[-1]
        combined_llm_result.scoring_items = all_scoring_items
        combined_llm_result.comment = comment
        combined_llm_result.final_score = final_keyword
    elif has_any_miss:
        # 有子题未命中但 LLM 全部失败
        from app.qwen_engine import QwenGradingResult
        combined_llm_result = QwenGradingResult(
            final_score=final_keyword,
            confidence=0.5,
            strategy='english_fallback',
            total_score=max_score,
            comment=comment,
            needs_review=True,
            scoring_items=all_scoring_items,
        )

    # layer_scores: keyword 层是精确匹配总分
    layer_scores['keyword'] = final_keyword
    layer_details['keyword'] = {
        'method': 'english_scoring_point',
        'sub_questions': all_keyword_details,
        'scoring_items': all_scoring_items,
        'comment': comment,
        'total_hits': sum(1 for item in all_scoring_items if item.get('hit')),
    }

    if combined_llm_result:
        layer_scores['llm'] = combined_llm_result.final_score
        layer_details['llm'] = {'reason': 'LLM兜底', 'sub_details': all_llm_details}
    else:
        layer_scores['llm'] = None
        layer_details['llm'] = {'reason': '全部精确命中，跳过LLM'}

    from app.three_layer_grader import _apply_strategy
    final_score = _apply_strategy(layer_scores, 'max')

    return {
        'final_score': final_score,
        'strategy': 'max',
        'layer_scores': layer_scores,
        'layer_details': layer_details,
        'llm_result': combined_llm_result,
    }
