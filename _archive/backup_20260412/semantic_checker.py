"""
语义相似度校验模块

使用本地 text2vec 模型对评分结果进行二次校验，
发现模型漏判的等价表达并自动纠偏。
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache

from loguru import logger


# 设置国内镜像（仅在模型未下载时生效）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


@lru_cache(maxsize=1)
def _load_model():
    """加载 text2vec 模型（全局单例，只加载一次）"""
    from sentence_transformers import SentenceTransformer
    model_path = 'shibing624/text2vec-base-chinese'
    logger.info(f"加载语义相似度模型: {model_path}")
    model = SentenceTransformer(model_path)
    logger.info("语义相似度模型加载完成")
    return model


def cosine_similarity(vec1, vec2) -> float:
    """计算两个向量的余弦相似度"""
    import numpy as np
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def compute_similarity(text1: str, text2: str) -> float:
    """计算两段文本的语义相似度"""
    model = _load_model()
    embeddings = model.encode([text1, text2])
    return cosine_similarity(embeddings[0], embeddings[1])


def extract_answer_segments(answer: str, keyword: str, context_chars: int = 30) -> List[str]:
    """
    从学生答案中提取包含关键词或其附近的文本片段

    Args:
        answer: 学生答案全文
        keyword: 要查找的关键词
        context_chars: 关键词前后保留的字符数

    Returns:
        匹配的文本片段列表
    """
    segments = []
    # 找关键词出现的位置
    for match in re.finditer(re.escape(keyword), answer):
        start = max(0, match.start() - context_chars)
        end = min(len(answer), match.end() + context_chars)
        segments.append(answer[start:end])

    # 如果没有精确匹配，按句子切分检查
    if not segments:
        sentences = re.split(r'[。；;，,\n]', answer)
        for sent in sentences:
            sent = sent.strip()
            if sent and len(sent) >= 2:
                segments.append(sent)
                # 额外按顿号、"和"、"及" 切出更短的短语片段，
                # 提高近义词（如"民营经济" vs "非公有制经济"）的匹配精度
                sub_parts = re.split(r'[、和及]', sent)
                for sp in sub_parts:
                    sp = sp.strip()
                    if 2 <= len(sp) <= 15 and sp not in segments:
                        segments.append(sp)

    return segments if segments else [answer]


def check_synonym_hit(
    answer: str,
    standard_keyword: str,
    synonym_list: List[str],
    threshold: float = 0.75,
) -> Tuple[bool, str, float]:
    """
    检查学生答案中是否包含关键词的等价表达

    Args:
        answer: 学生答案
        standard_keyword: 标准关键词（如"非公有制经济"）
        synonym_list: 等价词列表（如["民营经济", "私营经济"]）
        threshold: 语义相似度阈值，高于此值认为等价

    Returns:
        (是否命中, 命中的词/原因, 相似度分数)
    """
    # 1. 先检查精确匹配
    if standard_keyword in answer:
        return True, standard_keyword, 1.0

    # 2. 检查等价词列表
    for syn in synonym_list:
        if syn in answer:
            return True, syn, 1.0

    # 3. 语义相似度检查
    model = _load_model()
    segments = extract_answer_segments(answer, standard_keyword)

    best_sim = 0.0
    best_segment = ""

    # 编码标准关键词
    keyword_emb = model.encode(standard_keyword)

    for segment in segments:
        seg_emb = model.encode(segment)
        sim = cosine_similarity(keyword_emb, seg_emb)
        if sim > best_sim:
            best_sim = sim
            best_segment = segment

    if best_sim >= threshold:
        return True, f"语义匹配:{best_segment[:20]}...({best_sim:.2f})", best_sim

    return False, "", best_sim


def validate_scoring_items(
    answer: str,
    scoring_items: List[Dict[str, Any]],
    rubric_points: List[Dict[str, Any]],
    similarity_threshold: float = 0.75,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    用语义相似度校验模型的评分结果

    Args:
        answer: 学生答案
        scoring_items: 模型返回的评分要点列表
        rubric_points: 评分标准要点列表（含 keywords 等）
        similarity_threshold: 语义相似度阈值

    Returns:
        (校验后的 scoring_items, 变更日志列表)
    """
    changes = []

    if not scoring_items or not rubric_points:
        return scoring_items, changes

    # 构建 rubric 要点的关键词映射
    # rubric_points 格式: [{"description": "...", "keywords": ["..."]}, ...]
    point_keywords = {}
    for i, point in enumerate(rubric_points):
        keywords = point.get("keywords", [])
        if keywords:
            point_keywords[i] = keywords

    # 收集已命中要点的文本，用于排除误匹配
    hit_texts = []
    for item in scoring_items:
        if isinstance(item, dict) and item.get("hit", False):
            hit_texts.append(item.get("name", ""))
            hit_texts.append(item.get("reason", ""))
            hit_texts.append(item.get("quoted_text", ""))
    # 也加入 rubric 中已命中要点的描述
    hit_indices = set()
    for item_idx, item in enumerate(scoring_items):
        if isinstance(item, dict) and item.get("hit", False):
            if item_idx < len(rubric_points):
                hit_indices.add(item_idx)
    for hi in hit_indices:
        hit_texts.append(rubric_points[hi].get("description", ""))

    for item_idx, item in enumerate(scoring_items):
        if not isinstance(item, dict):
            continue

        item_name = item.get("name", "")
        is_hit = item.get("hit", False)

        # 只校验模型判未命中的要点
        if is_hit:
            continue

        # 在 rubric_points 中找到对应的要点：优先按顺序匹配，其次按描述包含匹配
        matched_point_idx = None
        if item_idx < len(rubric_points):
            matched_point_idx = item_idx
        else:
            for idx, point in enumerate(rubric_points):
                desc = point.get("description", "")
                if desc and (desc in item_name or item_name in desc):
                    matched_point_idx = idx
                    break

        if matched_point_idx is None:
            continue

        keywords = point_keywords.get(matched_point_idx, [])
        if not keywords:
            continue

        # 对每个关键词检查是否在学生答案中出现或有等价表达
        for keyword in keywords:
            if keyword in answer:
                # 检查关键词是否只是已命中要点文本的子串（避免误匹配）
                is_substring_of_hit = any(
                    keyword in ht and keyword != ht
                    for ht in hit_texts if ht
                )
                if is_substring_of_hit:
                    continue  # 该关键词已包含在其他要点的文本中，跳过

                # 精确命中但模型判了 false，需要纠正
                item["hit"] = True
                item["score"] = item.get("max_score", 0)
                item["reason"] = f"系统校验：发现关键词「{keyword}」"
                changes.append({
                    "item": item_name,
                    "keyword": keyword,
                    "action": "精确关键词覆盖",
                    "original_hit": False,
                    "new_hit": True,
                })
                break
            else:
                # 语义相似度检查
                model = _load_model()
                segments = extract_answer_segments(answer, keyword)
                keyword_emb = model.encode(keyword)

                for seg in segments:
                    seg_emb = model.encode(seg)
                    sim = cosine_similarity(keyword_emb, seg_emb)
                    if sim >= similarity_threshold:
                        item["hit"] = True
                        item["score"] = item.get("max_score", 0)
                        item["reason"] = f"系统校验：「{seg[:15]}...」与「{keyword}」语义相似度{sim:.2f}"
                        changes.append({
                            "item": item_name,
                            "keyword": keyword,
                            "matched_segment": seg[:30],
                            "similarity": round(sim, 3),
                            "action": "语义相似度覆盖",
                            "original_hit": False,
                            "new_hit": True,
                        })
                        break
                if item["hit"]:
                    break

    return scoring_items, changes
