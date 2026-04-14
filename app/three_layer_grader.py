"""
三层并行评分模块

第1层：关键词匹配
第2层：向量匹配度（满分答案相似度）
第3层：LLM 评分（现有引擎）

三层并行执行，根据策略取最终得分：max / min / avg / median

英语科目：通过 app.english_grader.grade_english() 独立评分
"""

import asyncio
import os
import re
from typing import Dict, Any, List, Tuple

from loguru import logger


def _apply_strategy(scores: Dict[str, float], strategy: str) -> float:
    """根据策略从三层得分中计算最终得分"""
    vals = [v for v in scores.values() if v is not None]
    if not vals:
        return 0.0

    if strategy == 'max':
        return max(vals)
    elif strategy == 'min':
        return min(vals)
    elif strategy == 'avg':
        return round(sum(vals) / len(vals), 2)
    elif strategy == 'median':
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        if n == 1:
            return vals_sorted[0]
        elif n % 2 == 1:
            return vals_sorted[n // 2]
        else:
            return round((vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2, 2)
    else:
        # 默认 avg
        return round(sum(vals) / len(vals), 2)


def keyword_match_score(answer: str, question_answers: List[Dict], max_score: float) -> Tuple[float, Dict]:
    """
    第1层：关键词匹配

    遍历采分点，检查关键词是否出现在学生答案中。
    每个采分点命中得该采分点的满分（按 score_ratio 折算）。
    返回 (得分, 详情)
    """
    scoring_points = [a for a in question_answers if a.get('scope_type') == 'scoring_point']
    if not scoring_points:
        return None, {'reason': 'no_scoring_points'}

    # 清理学生答案用于匹配
    answer_clean = re.sub(r'\s+', '', answer.lower())

    # 每个采分点的满分 = max_score / 采分点数
    point_score = max_score / len(scoring_points)
    total = 0.0
    details = []

    for sp in scoring_points:
        keyword = sp.get('answer_text', '').strip()
        label = sp.get('label', '')

        # 清理关键词（去掉括号内的说明）
        keyword_clean = re.sub(r'[（(].*?[)）]', '', keyword).strip()
        keyword_lower = keyword_clean.lower()
        keyword_nospace = re.sub(r'\s+', '', keyword_lower)

        matched = False
        if keyword_nospace and keyword_nospace in answer_clean:
            matched = True

        if matched:
            score = point_score * sp.get('score_ratio', 1.0)
            total += score
            details.append({'label': label, 'keyword': keyword_clean, 'matched': True, 'score': score})
        else:
            details.append({'label': label, 'keyword': keyword_clean, 'matched': False, 'score': 0})

    return round(min(total, max_score), 2), {'items': details, 'method': 'keyword'}


def vector_match_score(answer: str, question_answers: List[Dict], max_score: float) -> Tuple[float, Dict]:
    """
    第2层：向量匹配度

    计算学生答案与满分答案库的向量相似度，取最高相似度 × 满分。
    返回 (得分, 详情)
    """
    try:
        from app.semantic_checker import compute_similarity
    except Exception as e:
        logger.warning(f"向量模型加载失败: {e}")
        return None, {'reason': 'model_load_failed', 'error': str(e)}

    standard_answers = [a for a in question_answers if a.get('scope_type') == 'question' and a.get('answer_text')]
    if not standard_answers:
        return None, {'reason': 'no_standard_answers'}

    best_similarity = 0.0
    best_label = ''

    for sa in standard_answers:
        try:
            sim = compute_similarity(answer, sa['answer_text'])
            if sim > best_similarity:
                best_similarity = sim
                best_label = sa.get('label', '')
        except Exception as e:
            logger.warning(f"向量相似度计算失败: {e}")
            continue

    score = round(best_similarity * max_score, 2)
    return score, {'similarity': best_similarity, 'matched_label': best_label, 'method': 'vector'}


async def three_layer_grade(
    grading_engine,
    question: str,
    answer: str,
    rubric: Dict[str, Any],
    max_score: float,
    subject: str,
    question_answers: List[Dict],
    strategy: str = 'avg',
) -> Dict[str, Any]:
    """
    三层并行评分

    Args:
        grading_engine: QwenGradingEngine 实例
        question: 题目内容
        answer: 学生答案
        rubric: 评分标准字典
        max_score: 满分
        subject: 科目
        question_answers: 满分答案列表（从 question_answers 表查）
        strategy: 取分策略 max/min/avg/median

    Returns:
        {
            'final_score': float,
            'strategy': str,
            'layer_scores': {'keyword': float|None, 'vector': float|None, 'llm': float},
            'layer_details': {...},
            'llm_result': QwenGradingResult,
        }
    """
    layer_scores = {'keyword': None, 'vector': None, 'llm': None}
    layer_details = {'keyword': {}, 'vector': {}, 'llm': {}}
    llm_result = None

    _debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    _answer_preview = answer[:80] + ('...' if len(answer) > 80 else '')

    logger.debug(f"[三层评分] subject={subject}, strategy={strategy}, max_score={max_score}")
    if _debug:
        logger.debug(f"[三层评分] 答案: {_answer_preview}")

    # ===== 英语科目：交给独立模块 =====
    if subject == 'english':
        from app.english_grader import grade_english
        return await grade_english(
            answer=answer,
            question_answers=question_answers,
            max_score=max_score,
            grading_engine=grading_engine,
            question=question,
            rubric=rubric,
        )

    # ===== 非英语科目：三层并行 =====
    if _debug:
        logger.debug(f"[三层评分] 非英语科目，三层并行执行中...")

    # 第1层：关键词匹配（同步，快速）
    try:
        kw_score, kw_detail = keyword_match_score(answer, question_answers, max_score)
        layer_scores['keyword'] = kw_score
        layer_details['keyword'] = kw_detail
        if _debug:
            logger.debug(f"[三层评分] 第1层关键词匹配: score={kw_score}, reason={kw_detail.get('reason', 'hit')}")
    except Exception as e:
        logger.warning(f"关键词匹配异常: {e}")
        layer_details['keyword'] = {'error': str(e)}

    def run_vector():
        return vector_match_score(answer, question_answers, max_score)

    # 第3层：LLM 评分（异步）
    async def run_llm():
        return await grading_engine.grade(
            question=question,
            answer=answer,
            rubric=rubric,
            max_score=max_score,
            subject=subject,
        )

    # 并行执行第2层和第3层
    if _debug:
        logger.debug(f"[三层评分] 开始并行执行第2层(向量) + 第3层(LLM)")
    loop = asyncio.get_event_loop()
    vector_task = loop.run_in_executor(None, run_vector)
    llm_task = run_llm()
    (vec_score, vec_detail), llm_result = await asyncio.gather(vector_task, llm_task)
    layer_scores['vector'] = vec_score
    layer_details['vector'] = vec_detail
    layer_scores['llm'] = llm_result.final_score if llm_result else None
    layer_details['llm'] = llm_result.dict() if llm_result else {}

    if _debug:
        logger.debug(f"[三层评分] 第2层向量: score={vec_score}, 第3层LLM: score={llm_result.final_score if llm_result else 'FAILED'}")

    # 应用策略取分
    final_score = _apply_strategy(layer_scores, strategy)
    if _debug:
        logger.debug(f"[三层评分] 最终得分={final_score} (策略={strategy}, 各层={layer_scores})")

    return {
        'final_score': final_score,
        'strategy': strategy,
        'layer_scores': layer_scores,
        'layer_details': layer_details,
        'llm_result': llm_result,
    }
