"""
英语编辑器 AI 接口
"""
from flask import request, jsonify
from app.api_shared import api_bp
from app.api_shared import _call_llm_sync, _parse_json_from_llm, _check_subject_access
from loguru import logger


@api_bp.route('/english/extract', methods=['POST'])
def english_extract():
    """AI 提取子题+采分点"""
    data = request.json or {}
    full_text = data.get('full_text', '')
    if not full_text.strip():
        return jsonify({'success': False, 'error': 'full_text 不能为空'}), 400

    from app.english_prompts import EXTRACT_SUBQUESTIONS_SYSTEM, make_extract_prompt
    raw = _call_llm_sync(EXTRACT_SUBQUESTIONS_SYSTEM, make_extract_prompt(full_text))
    if not raw:
        return jsonify({'success': False, 'error': 'AI 调用失败'}), 500

    result = _parse_json_from_llm(raw)
    if not result or not result.get('sub_questions'):
        return jsonify({'success': False, 'error': 'AI 返回结果无效', 'raw': raw[:500]}), 500

    return jsonify({'success': True, 'data': result})


@api_bp.route('/english/extract-scoring-points', methods=['POST'])
def english_extract_scoring_points():
    """从已知子题中提取采分点（不含子题拆分）"""
    data = request.json or {}
    question_text = data.get('question_text', '')
    standard_answer = data.get('standard_answer', '')
    if not question_text.strip() or not standard_answer.strip():
        return jsonify({'success': False, 'error': 'question_text 和 standard_answer 不能为空'}), 400

    max_score = data.get('max_score', 0)

    from app.english_prompts import EXTRACT_SCORING_POINTS_SYSTEM, make_extract_scoring_points_prompt
    user_prompt = make_extract_scoring_points_prompt(question_text, standard_answer, max_score)
    raw = _call_llm_sync(EXTRACT_SCORING_POINTS_SYSTEM, user_prompt)
    if not raw:
        return jsonify({'success': False, 'error': 'AI 调用失败'}), 500

    result = _parse_json_from_llm(raw)
    if not result or not result.get('scoring_points'):
        return jsonify({'success': False, 'error': 'AI 返回结果无效', 'raw': raw[:500]}), 500

    return jsonify({'success': True, 'data': result})


@api_bp.route('/english/suggest-synonyms', methods=['POST'])
def english_suggest_synonyms():
    """AI 同义词补全"""
    data = request.json or {}
    keyword = data.get('keyword', '')
    if not keyword.strip():
        return jsonify({'success': False, 'error': 'keyword 不能为空'}), 400

    from app.english_prompts import SUGGEST_SYNONYMS_SYSTEM, make_synonyms_prompt
    user_prompt = make_synonyms_prompt(
        keyword=keyword,
        context=data.get('context', ''),
        question_text=data.get('question_text', ''),
        existing_synonyms=data.get('existing_synonyms', []),
    )
    raw = _call_llm_sync(SUGGEST_SYNONYMS_SYSTEM, user_prompt)
    if not raw:
        return jsonify({'success': False, 'error': 'AI 调用失败'}), 500

    result = _parse_json_from_llm(raw)
    suggestions = result.get('suggestions', [])
    # 过滤 confidence < 0.5 和已存在的
    existing = set(s.lower() for s in data.get('existing_synonyms', []))
    existing.add(keyword.lower())
    filtered = [s for s in suggestions if s.get('confidence', 0) >= 0.5 and s.get('term', '').lower() not in existing]
    return jsonify({'success': True, 'data': filtered})


@api_bp.route('/english/suggest-exclude', methods=['POST'])
def english_suggest_exclude():
    """AI 排除词建议"""
    data = request.json or {}
    keywords = data.get('keywords', [])
    if not keywords:
        return jsonify({'success': False, 'error': 'keywords 不能为空'}), 400

    from app.english_prompts import SUGGEST_EXCLUDE_SYSTEM, make_exclude_prompt
    user_prompt = make_exclude_prompt(
        question_text=data.get('question_text', ''),
        keywords=keywords,
        synonyms=data.get('synonyms', []),
        context=data.get('context', ''),
    )
    raw = _call_llm_sync(SUGGEST_EXCLUDE_SYSTEM, user_prompt)
    if not raw:
        return jsonify({'success': False, 'error': 'AI 调用失败'}), 500

    result = _parse_json_from_llm(raw)
    return jsonify({'success': True, 'data': result.get('suggestions', [])})


@api_bp.route('/english/generate-rubric', methods=['POST'])
def english_generate_rubric():
    """AI 生成评分脚本"""
    data = request.json or {}
    question_text = data.get('question_text', '')
    if not question_text.strip():
        return jsonify({'success': False, 'error': 'question_text 不能为空'}), 400

    from app.english_prompts import GENERATE_RUBRIC_SCRIPT_SYSTEM, make_generate_rubric_prompt
    user_prompt = make_generate_rubric_prompt(
        question_text=question_text,
        standard_answer=data.get('standard_answer', ''),
        max_score=data.get('max_score', 2),
        scoring_config=data.get('scoring_config', []),
    )
    raw = _call_llm_sync(GENERATE_RUBRIC_SCRIPT_SYSTEM, user_prompt)
    if not raw:
        return jsonify({'success': False, 'error': 'AI 调用失败'}), 500

    return jsonify({'success': True, 'data': {'script': raw}})
