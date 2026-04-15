"""
一致性检查 / 命题质量评估 / 生成模拟答案 / AI 自动出题
"""
import json
import re
from flask import request, jsonify, session
from loguru import logger
from app.api_shared import (
    api_bp, grading_engine, _check_subject_access, _session_subject,
    RUBRIC_SCRIPT_SYSTEM_PROMPT, _call_llm_sync,
)
from app.models.db_models import (
    get_question, get_questions, add_question, add_test_case,
)
from app.english_prompts import (
    QUALITY_EVALUATION_SYSTEM_PROMPT_EN,
    AUTO_GEN_QUESTION_SYSTEM_EN,
    AUTO_GEN_TESTCASE_SYSTEM_EN,
    STYLE_GUIDE_EN,
    make_evaluate_question_prompt_en,
    make_auto_gen_question_prompt_en,
    make_auto_gen_rubric_prompt_en,
    make_auto_gen_testcase_prompt_en,
    make_evaluate_fallback_en,
)


QUALITY_EVALUATION_SYSTEM_PROMPT = """你是一位资深职业教育命题质量审查专家，负责在题目保存前发现潜在质量问题，避免无效命题导致后续评分工作全部白费。

你的任务：根据提供的题目信息，从4个维度对命题质量进行全面评估，输出结构化评估报告。

## 评估维度与检查项

### 一、题目本身（4项检查）
1. **题意模糊**：题目表述含糊，学生不知道要回答什么。例如只写"谈谈你的看法"而没有指明方向。
2. **存在歧义**：同一题目可以有多种理解，导致不同学生可能给出不同方向的回答。
3. **缺少限定条件**：题目范围太宽，标准答案无法涵盖所有正确回答，或学生不知道从哪个角度回答。
4. **与标准答案不匹配**：题目问的内容和标准答案答的内容不是同一个问题。例如题目问"是什么"但答案在解释"为什么"。

### 二、标准答案（4项检查）
5. **答案不完整**：标准答案缺少题目要求回答的关键内容。例如题目要求简述3个方面但答案只列了2个。
6. **答案有误**：标准答案包含错误或过时的知识点。
7. **要点模糊**：标准答案本身就有模糊表述，如"等"、"相关要点"等未展开的内容。
8. **与评分要点不一致**：标准答案列了N个要点，但评分要点/分数分布只覆盖其中一部分。

### 三、评分规则（4项检查）
9. **分值分配不合理**：各得分点分数之和不等于满分，或分配明显不均（一个要点占80%分值）。
10. **标准过于宽泛**：评分标准如"回答正确得满分"、"根据回答质量给分"，没有细分到具体判断条件。
11. **缺少部分得分规则**：没有定义部分答对怎么给分，所有要点都是全有或全无。
12. **关键词缺失**：评分要点没有提供判断关键词，阅卷者无法准确判断。

### 四、整体（2项检查）
13. **难度与分值不匹配**：明显简单的题目给了过高分值，或过于复杂的题目分值太低。
14. **题型不明确**：无法判断是简答题、论述题、名词解释还是填空题，不同题型的评分标准差异很大。

## 评分标准
- 基础分 100 分
- 每个 error 级别问题扣 15 分
- 每个 warning 级别问题扣 8 分
- 每个 info 级别问题扣 3 分
- overall_score = max(0, 100 - 总扣分)

## 判定规则
- overall_score >= 80 且无 error → verdict = "pass"
- 存在任意 error 或 overall_score < 60 → verdict = "fail"
- 其余 → verdict = "warning"

## 输出格式
严格输出以下 JSON，不要输出任何其他内容：
{"overall_score": 整数, "verdict": "pass"或"warning"或"fail", "issues": [{"category": "题目本身/标准答案/评分规则/整体", "severity": "info/warning/error", "description": "具体问题描述"}], "suggestions": ["改进建议1", "改进建议2"]}

## 重要原则
- 如果题目质量良好，issues 可以为空数组，overall_score 给 95-100
- suggestions 只在有问题时给出，针对具体问题提供可操作的修改建议
- 不要吹毛求疵，只报告确实影响评分准确性的问题
- 描述要具体，不要泛泛而谈，指出具体哪个部分有问题"""


AUTO_GEN_QUESTION_SYSTEM = """你是一位资深职业教育命题专家，专门为中等职业学校学生出题。

要求：
1. 题目必须是简答题或论述题（不要出选择题、填空题、判断题）
2. 题目要符合中职学生的知识水平，不要太难也不要太简单
3. 每道题必须有明确的标准答案，不能是开放性讨论题
4. 评分要点必须清晰、可量化

输出格式（严格 JSON）：
{
    "title": "简短题目标题（15字以内）",
    "content": "完整的题目内容",
    "max_score": 分值（整数）,
    "difficulty": "easy/medium/hard",
    "knowledge": "本题考查的知识点",
    "content_type": "简答题",
    "standard_answer": "完整的标准答案，包含所有得分要点",
    "rubric_rules": "整体评分规则说明",
    "rubric_points": "每行一个得分点，格式：要点描述 (X分)"
}

注意：
- rubric_points 中各要点分值之和必须等于 max_score
- 标准答案要完整、准确，适合做评分参照
- 不要输出任何 JSON 以外的内容"""

AUTO_GEN_TESTCASE_SYSTEM = """你是一位经验丰富的阅卷老师，熟悉各类考生作答模式。

你的任务：根据题目和标准答案，生成多份模拟考生作答，覆盖不同的得分水平。

输出格式（严格 JSON 数组）：
[
    {
        "description": "简短描述",
        "case_type": "ai_generated",
        "answer_text": "模拟的考生作答内容",
        "expected_score": 期望分数
    }
]

注意：expected_score 必须是具体数字，分数应形成梯度分布。不要输出任何 JSON 以外的内容。"""

SUBJECT_TOPICS = {
    'politics': ['中国特色社会主义', '经济与社会', '政治与法治', '哲学与人生', '职业道德与法治', '心理健康与职业生涯'],
    'chinese': ['现代文阅读理解', '古诗词鉴赏', '文言文翻译与理解', '语言表达与应用', '写作基础知识', '中国传统文化常识'],
    'english': ['阅读理解', '语法与词汇', '翻译（中译英/英译中）', '情景交际', '书面表达基础', '时态与语态'],
}


@api_bp.route('/check-consistency', methods=['POST'])
def check_consistency():
    """检查原题与题干/答案/规则之间的一致性，以及分值之和是否等于满分"""
    data = request.json
    original_text = data.get('originalText', '').strip()
    content = data.get('content', '').strip()
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_rules = data.get('rubricRules', '').strip()
    rubric_points_raw = data.get('rubricPoints', '')
    # rubricPoints 可以是字符串或数组（前端可能传数组形式）
    if isinstance(rubric_points_raw, list):
        rubric_points = '\n'.join(
            f"{p.get('text', p.get('label', ''))} ({p.get('score', 0)}分)"
            for p in rubric_points_raw if isinstance(p, dict)
        )
    else:
        rubric_points = (rubric_points_raw or '').strip()
    max_score = data.get('maxScore', 10)
    logger.debug(f"[check-consistency] maxScore={max_score}, rubricPoints类型={type(rubric_points_raw).__name__}, rubricPoints[:100]={str(rubric_points)[:100]}")

    def normalize(s):
        return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', s or ''))

    issues = []

    # 提取原文中的满分值：匹配 "（N分）" 或 "（N 分）" 但排除小题分值
    orig_total_score = None
    if original_text:
        score_matches = re.findall(r'[(（](\d+\.?\d*)\s*(分|points?|marks?)[)）]', original_text)
        if score_matches:
            all_scores = [float(s[0]) if isinstance(s, tuple) else float(s) for s in score_matches]
            # 策略：只有 ≥5 分的才认为是总分（小题分值一般 ≤5）
            candidates = [s for s in all_scores if s >= 5]
            if candidates:
                orig_total_score = max(candidates)

    # 提取分数分布各点之和
    rubric_total = None
    if rubric_points:
        scores = re.findall(r'[(（](\d+\.?\d*)\s*分', rubric_points)
        if scores:
            rubric_total = sum(float(s) for s in scores)

    # 推断"正确"的满分：原文满分是权威来源
    inferred_score = None
    if orig_total_score is not None and rubric_total is not None:
        if abs(orig_total_score - rubric_total) < 0.01:
            # 两者一致 → 这就是正确满分
            inferred_score = orig_total_score
        else:
            # 两者不一致 → 以原文为准，分数分布需要修正
            inferred_score = orig_total_score
            issues.append({
                'type': 'orig_vs_rubric_mismatch',
                'field': 'rubricPoints',
                'desc': f'原文标注满分 {orig_total_score} 分，分数分布合计 {rubric_total} 分，两者不一致',
                'suggestion': f'分数分布各点之和应为 {orig_total_score} 分，当前加起来是 {rubric_total} 分，请检查各要点分值'
            })
    elif orig_total_score is not None:
        inferred_score = orig_total_score
    elif rubric_total is not None:
        inferred_score = rubric_total

    # 用推断出的满分检查表单的 maxScore
    if inferred_score is not None and abs(inferred_score - max_score) > 0.01:
        issues.append({
            'type': 'form_score_wrong',
            'field': 'score',
            'desc': f'表单满分 {max_score} 分不正确，应为 {inferred_score} 分',
            'suggestion': f'请将满分值修改为 {inferred_score}',
            'original_value': str(inferred_score)
        })

    # 3. 原文 vs 题干：原文中有关键内容在题干中缺失
    if original_text and content:
        orig_match = re.search(r'题目[：:]\s*(.*?)(?=标准答案|评分规则|$)', original_text, re.DOTALL)
        if orig_match:
            orig_question = orig_match.group(1).strip()
        else:
            orig_question = original_text

        # 如果题干明显比原文题目部分短，可能有遗漏
        if len(normalize(content)) < len(normalize(orig_question)) * 0.7:
            issues.append({
                'type': 'content_shorter',
                'field': 'content',
                'desc': f'题干（{len(normalize(content))}字）比原题（{len(normalize(orig_question))}字）短很多，可能有内容遗漏',
                'suggestion': '请对比原题检查题干是否完整',
                'original_value': orig_question
            })

    # 4. 原文 vs 标准答案
    if original_text and standard_answer:
        orig_match_ans = re.search(r'标准答案[：:]\s*(.*?)(?=评分规则|$)', original_text, re.DOTALL)
        if orig_match_ans:
            orig_answer = orig_match_ans.group(1).strip()
            if len(normalize(standard_answer)) < len(normalize(orig_answer)) * 0.7:
                issues.append({
                    'type': 'answer_shorter',
                    'field': 'standardAnswer',
                    'desc': f'标准答案（{len(normalize(standard_answer))}字）比原题中的答案（{len(normalize(orig_answer))}字）短很多',
                    'suggestion': '请对比原题检查标准答案是否完整',
                    'original_value': orig_answer
                })

    # 5. 原文 vs 评分规则
    if original_text and rubric_rules:
        orig_match_rules = re.search(r'评分规则[：:]\s*(.*?)(?=【简答题|$)', original_text, re.DOTALL)
        if orig_match_rules:
            orig_rules = orig_match_rules.group(1).strip()
            if len(normalize(rubric_rules)) < len(normalize(orig_rules)) * 0.7:
                issues.append({
                    'type': 'rules_shorter',
                    'field': 'rubricRules',
                    'desc': f'评分规则（{len(normalize(rubric_rules))}字）比原题中的规则（{len(normalize(orig_rules))}字）短很多',
                    'suggestion': '请对比原题检查评分规则是否完整',
                    'original_value': orig_rules
                })

    # 6. 原文标准答案中的小题分值 vs 分数分布
    if original_text and rubric_points:
        orig_match_ans = re.search(r'标准答案[：:]\s*(.*?)(?=评分规则|$)', original_text, re.DOTALL)
        if orig_match_ans:
            orig_answer_text = orig_match_ans.group(1)
            orig_point_scores = re.findall(r'[(（](\d+\.?\d*)\s*分', orig_answer_text)
            rubric_point_scores = re.findall(r'[(（](\d+\.?\d*)\s*分', rubric_points)
            if orig_point_scores and rubric_point_scores:
                orig_total = sum(float(s) for s in orig_point_scores)
                rubric_total = sum(float(s) for s in rubric_point_scores)
                if abs(orig_total - rubric_total) > 0.01:
                    issues.append({
                        'type': 'points_mismatch',
                        'field': 'rubricPoints',
                        'desc': f'原文答案中各题分值合计 {orig_total} 分 ≠ 分数分布合计 {rubric_total} 分',
                        'suggestion': f'请检查分数分布是否与原文答案中的分值一致'
                    })

    return jsonify({
        'success': True,
        'data': {
            'issues': issues,
            'pass': len(issues) == 0
        }
    })


@api_bp.route('/batch-check-consistency', methods=['POST'])
def batch_check_consistency():
    """按科目批量检查所有题目的一致性"""
    data = request.json
    subject = data.get('subject', '').strip()
    if not subject:
        return jsonify({'success': False, 'error': '请指定科目'}), 400
    # 非 admin 强制用 session.subject
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj

    questions = [q for q in get_questions() if q.get('subject') == subject]
    if not questions:
        return jsonify({'success': False, 'error': f'科目「{subject}」下没有题目'}), 400

    def normalize(s):
        return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', s or ''))

    def check_one(q):
        issues = []
        original_text = (q.get('original_text') or '').strip()
        content = (q.get('content') or '').strip()
        standard_answer = (q.get('standard_answer') or '').strip()
        rubric_rules = (q.get('rubric_rules') or '').strip()
        rubric_points = (q.get('rubric_points') or '').strip()
        max_score = q.get('max_score', 10) or 10

        # 原文满分（≥5分的才认为是总分）
        orig_total_score = None
        if original_text:
            score_matches = re.findall(r'[(（](\d+\.?\d*)\s*(分|points?|marks?)[)）]', original_text)
            if score_matches:
                candidates = [float(s[0]) if isinstance(s, tuple) else float(s) for s in score_matches if float(s[0] if isinstance(s, tuple) else s) >= 5]
                if candidates:
                    orig_total_score = max(candidates)

        # 1. 原文满分 vs 表单满分
        if orig_total_score is not None and abs(orig_total_score - max_score) > 0.01:
            issues.append(f'原文满分{orig_total_score}分 ≠ 表单满分{max_score}分')

        # 2. 分数分布各点之和 vs 表单满分
        if rubric_points:
            scores = re.findall(r'[(（](\d+\.?\d*)\s*分', rubric_points)
            if scores:
                total = sum(float(s) for s in scores)
                if abs(total - max_score) > 0.01:
                    issues.append(f'分数分布合计{total}分 ≠ 满分{max_score}分')

        # 3. 原文 vs 题干
        if original_text and content:
            orig_match = re.search(r'题目[：:]\s*(.*?)(?=标准答案|评分规则|$)', original_text, re.DOTALL)
            orig_question = orig_match.group(1).strip() if orig_match else original_text
            if len(normalize(content)) < len(normalize(orig_question)) * 0.7:
                issues.append(f'题干比原题短很多（{len(normalize(content))}字 vs {len(normalize(orig_question))}字）')

        # 4. 原文 vs 标准答案
        if original_text and standard_answer:
            orig_match_ans = re.search(r'标准答案[：:]\s*(.*?)(?=评分规则|$)', original_text, re.DOTALL)
            if orig_match_ans:
                orig_answer = orig_match_ans.group(1).strip()
                if len(normalize(standard_answer)) < len(normalize(orig_answer)) * 0.7:
                    issues.append(f'标准答案比原题中的答案短很多')

        # 5. 原文 vs 评分规则
        if original_text and rubric_rules:
            orig_match_rules = re.search(r'评分规则[：:]\s*(.*?)(?=【简答题|$)', original_text, re.DOTALL)
            if orig_match_rules:
                orig_rules = orig_match_rules.group(1).strip()
                if len(normalize(rubric_rules)) < len(normalize(orig_rules)) * 0.7:
                    issues.append(f'评分规则比原题中的规则短很多')

        # 6. 原文答案中小题分值 vs 分数分布
        if original_text and rubric_points:
            orig_match_ans = re.search(r'标准答案[：:]\s*(.*?)(?=评分规则|$)', original_text, re.DOTALL)
            if orig_match_ans:
                orig_point_scores = re.findall(r'[(（](\d+\.?\d*)\s*分', orig_match_ans.group(1))
                rubric_point_scores = re.findall(r'[(（](\d+\.?\d*)\s*分', rubric_points)
                if orig_point_scores and rubric_point_scores:
                    orig_total = sum(float(s) for s in orig_point_scores)
                    rubric_total = sum(float(s) for s in rubric_point_scores)
                    if abs(orig_total - rubric_total) > 0.01:
                        issues.append(f'原文答案分值合计{orig_total}分 ≠ 分数分布合计{rubric_total}分')

        return issues

    results = []
    for q in questions:
        issues = check_one(q)
        if issues:
            results.append({
                'id': q['id'],
                'question_number': q.get('question_number', ''),
                'title': (q.get('content') or '')[:50],
                'issues': issues
            })

    return jsonify({
        'success': True,
        'data': {
            'total': len(questions),
            'problems': results,
            'problem_count': len(results),
            'pass': len(results) == 0
        }
    })


@api_bp.route('/evaluate-question', methods=['POST'])
def evaluate_question():
    """AI 命题质量评估"""
    data = request.json
    original_text = data.get('originalText', '').strip()
    content = data.get('content', '').strip()
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_points = data.get('rubricPoints', '').strip()
    rubric_rules = data.get('rubricRules', '').strip()
    max_score = data.get('maxScore', 10)
    difficulty = data.get('difficulty', '')
    content_type = data.get('contentType', '')
    subject = data.get('subject', 'general')
    # 非 admin 强制用 session.subject
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj

    if not content and not original_text:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空，无法评估质量'}), 400

    is_english = subject == 'english'

    if is_english:
        user_prompt = make_evaluate_question_prompt_en(
            content=content, max_score=max_score, standard_answer=standard_answer,
            rubric_points=rubric_points, rubric_rules=rubric_rules,
            difficulty=difficulty, content_type=content_type, original_text=original_text,
        )
        system_prompt = QUALITY_EVALUATION_SYSTEM_PROMPT_EN
        fallback_result = make_evaluate_fallback_en()
    else:
        if original_text:
            user_prompt = f"""请评估以下命题的质量：

【原始命题原文】
{original_text}

【满分】
{max_score} 分"""
        else:
            user_prompt = f"""请评估以下命题的质量：

【题目内容】
{content}

【满分】
{max_score} 分"""

        if standard_answer:
            user_prompt += f"\n\n【标准答案】\n{standard_answer}"
        if rubric_points:
            user_prompt += f"\n\n【分数分布/得分要点】\n{rubric_points}"
        if rubric_rules:
            user_prompt += f"\n\n【评分规则】\n{rubric_rules}"
        if difficulty:
            difficulty_map = {'easy': '简单', 'medium': '中等', 'hard': '困难'}
            user_prompt += f"\n\n【难度】\n{difficulty_map.get(difficulty, difficulty)}"
        if content_type:
            user_prompt += f"\n\n【题型】\n{content_type}"

        user_prompt += "\n\n请按照评估维度逐项检查，输出评估报告 JSON。"
        system_prompt = QUALITY_EVALUATION_SYSTEM_PROMPT
        fallback_result = {
            'overall_score': 50,
            'verdict': 'warning',
            'issues': [{'category': '整体', 'severity': 'warning', 'description': 'AI 评估未能返回有效结果，请人工检查'}],
            'suggestions': ['建议人工审核题目质量'],
        }

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()

        # 解析 JSON：先尝试直接解析，再用正则兜底
        result = None
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if not result or not isinstance(result, dict):
            logger.warning(f"质量评估 JSON 解析失败，原始响应: {raw[:200]}")
            return jsonify({'success': True, 'data': fallback_result})

        # 结构校验和修正
        score = result.get('overall_score', 50)
        if not isinstance(score, (int, float)):
            score = 50
        score = max(0, min(100, int(score)))

        verdict = result.get('verdict', 'warning')
        if verdict not in ('pass', 'warning', 'fail'):
            # 根据分数重新判定
            if score >= 80:
                verdict = 'pass'
            elif score < 60:
                verdict = 'fail'
            else:
                verdict = 'warning'

        issues = result.get('issues', [])
        if not isinstance(issues, list):
            issues = []
        suggestions = result.get('suggestions', [])
        if not isinstance(suggestions, list):
            suggestions = []

        validated = {
            'overall_score': score,
            'verdict': verdict,
            'issues': issues,
            'suggestions': suggestions
        }

        logger.info(f"命题质量评估完成: score={score}, verdict={verdict}, issues={len(issues)}")

        # 如果传了 question_id，直接更新数据库中的 quality_score
        question_id = data.get('question_id') or data.get('questionId')
        if question_id:
            try:
                from app.models.db_models import get_db_connection
                conn = get_db_connection()
                conn.execute('UPDATE questions SET quality_score = ? WHERE id = ?', (score, int(question_id)))
                conn.commit()
                conn.close()
                logger.info(f"题目 {question_id} 质量分数已更新: {score}")
            except Exception as e:
                logger.warning(f"更新 quality_score 失败: {e}")

        return jsonify({'success': True, 'data': validated})

    except Exception as e:
        logger.error(f"命题质量评估失败：{e}")
        return jsonify({'success': True, 'data': fallback_result})


@api_bp.route('/generate-answer', methods=['POST'])
def generate_answer():
    """为指定题目生成一份模拟学生答案（供人工评分）"""
    data = request.json or {}
    question_id = data.get('question_id')

    if not question_id:
        return jsonify({'success': False, 'error': 'question_id 不能为空'}), 400

    q = get_question(int(question_id))
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权操作其他科目的题目'}), 403

    content = q.get('content', '')
    max_score = q.get('max_score', 10)
    standard_answer = q.get('standard_answer', '')

    if not content:
        return jsonify({'success': False, 'error': '题目内容为空'}), 400

    # 随机选择一个水平
    import random
    levels = [
        ('优秀作答', 0.85, 1.0),
        ('良好作答', 0.65, 0.85),
        ('中等作答', 0.45, 0.65),
        ('偏低作答', 0.2, 0.45),
        ('较差作答', 0.0, 0.2),
    ]
    level_name, ratio_low, ratio_high = random.choice(levels)
    target_score = round(random.uniform(ratio_low * max_score, ratio_high * max_score), 1)

    system_prompt = f"""你是一位中等职业学校的学生，正在回答考试题目。

要求：
1. 模拟真实学生的作答，不要写得太完美
2. 根据目标水平作答：{level_name}（目标得分约 {target_score} 分，满分 {max_score} 分）
3. 作答要像真实学生写的，可以有口语化表达、语句不完整等情况
4. 只输出学生答案的纯文本内容，不要任何解释、标题或格式标记"""

    user_prompt = f"""【题目】
{content}

【标准答案（仅供参考，不要照抄）】
{standard_answer}

请以学生的口吻作答，目标水平：{level_name}。"""

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()

        if not answer or len(answer) < 10:
            return jsonify({'success': False, 'error': '生成的答案过短，请重试'}), 500

        return jsonify({
            'success': True,
            'data': {
                'answer': answer,
                'level': level_name,
                'target_score': target_score,
            }
        })
    except Exception as e:
        logger.error(f"生成模拟答案失败: {e}")
        return jsonify({'success': False, 'error': f'生成失败：{str(e)}'}), 500


@api_bp.route('/auto-generate', methods=['POST'])
def auto_generate():
    """AI 自动出题 + 评分脚本 + 测试用例 — 非 admin 强制 subject = session.subject"""
    import random
    data = request.json or {}
    subject = data.get('subject', 'politics')
    # 科目访问控制
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj  # 非 admin 强制用 session 科目
    count = min(int(data.get('count', 5)), 50)
    testcase_count = min(int(data.get('testcase_count', 5)), 10)
    topic = data.get('topic', '')

    topics = SUBJECT_TOPICS.get(subject, SUBJECT_TOPICS['politics'])

    # 获取已有标题用于去重
    existing_qs = get_questions(subject)
    existing_titles = [q.get('title', '') for q in existing_qs if q.get('title')]

    results = []
    for i in range(count):
        t = topic or topics[i % len(topics)]
        score = random.randint(5, 10)
        difficulty = random.choice(['easy', 'medium', 'hard'])
        diff_cn = {'easy': '简单', 'medium': '中等', 'hard': '困难'}[difficulty]

        hint = f"已有题目（请勿重复）：{', '.join(existing_titles[:5])}" if existing_titles else ""

        is_english = subject == 'english'
        if is_english:
            question_system = AUTO_GEN_QUESTION_SYSTEM_EN
            user_prompt = make_auto_gen_question_prompt_en(t, score, difficulty, hint)
        else:
            question_system = AUTO_GEN_QUESTION_SYSTEM
            user_prompt = f"""请为【{subject}】科目出一道关于【{t}】的简答题。

要求：
- 适用对象：湖南省中等职业学校2年级学生
- 分值：{score} 分
- 难度：{diff_cn}
- 知识领域：{t}

{hint}

请直接输出 JSON，不要任何解释。"""

        try:
            resp = grading_engine.client.chat.completions.create(
                model=grading_engine.model,
                messages=[
                    {"role": "system", "content": question_system},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2046,
            )
            raw = resp.choices[0].message.content.strip()
            qdata = None
            try:
                qdata = json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*\}', raw)
                if m:
                    qdata = json.loads(m.group())

            if not qdata or not qdata.get('content'):
                logger.warning(f"自动出题第{i+1}道：解析失败")
                continue

            # 生成评分脚本
            rubric_script = None
            try:
                if is_english:
                    rubric_system = RUBRIC_SCRIPT_SYSTEM_PROMPT_EN
                    rubric_user = make_auto_gen_rubric_prompt_en(
                        content=qdata['content'],
                        max_score=qdata.get('max_score', score),
                        standard_answer=qdata.get('standard_answer', ''),
                        rubric_rules=qdata.get('rubric_rules', ''),
                        rubric_points=qdata.get('rubric_points', ''),
                    )
                else:
                    rubric_system = RUBRIC_SCRIPT_SYSTEM_PROMPT
                    rubric_user = f"""请根据以下信息生成结构化评分脚本：

【题目内容】
{qdata['content']}

【满分】
{qdata.get('max_score', score)} 分

【标准答案】
{qdata.get('standard_answer', '')}

【评分规则】
{qdata.get('rubric_rules', '无')}

【分数分布/得分要点】
{qdata.get('rubric_points', '无')}

请直接输出评分脚本，不要任何解释。"""

                rs_resp = grading_engine.client.chat.completions.create(
                    model=grading_engine.model,
                    messages=[
                        {"role": "system", "content": rubric_system},
                        {"role": "user", "content": rubric_user}
                    ],
                    temperature=0.0,
                    max_tokens=4096,
                )
                rubric_script = rs_resp.choices[0].message.content.strip()
                if len(rubric_script) < 50:
                    rubric_script = None
            except Exception as e:
                logger.warning(f"生成评分脚本失败: {e}")

            # 保存题目
            title = qdata.get('title', qdata['content'][:30])
            rubric_json = json.dumps({
                'rubricRules': qdata.get('rubric_rules', ''),
                'points': [{'description': p.strip()} for p in qdata.get('rubric_points', '').split('\n') if p.strip()],
                'rubricScript': rubric_script or '',
                'knowledge': qdata.get('knowledge', t),
                'contentType': qdata.get('content_type', '简答题'),
                'standardAnswer': qdata.get('standard_answer', ''),
            }, ensure_ascii=False)

            qid = add_question(
                subject=subject,
                title=title,
                content=qdata['content'],
                original_text=qdata['content'],
                standard_answer=qdata.get('standard_answer', ''),
                rubric_rules=qdata.get('rubric_rules', ''),
                rubric_points=qdata.get('rubric_points', ''),
                rubric_script=rubric_script or '',
                rubric=rubric_json,
                max_score=float(qdata.get('max_score', score))
            )

            # 生成测试用例
            tc_saved = 0
            try:
                if is_english:
                    tc_system = AUTO_GEN_TESTCASE_SYSTEM_EN
                    tc_user = make_auto_gen_testcase_prompt_en(
                        content=qdata['content'],
                        max_score=qdata.get('max_score', score),
                        standard_answer=qdata.get('standard_answer', ''),
                        rubric_points=qdata.get('rubric_points', ''),
                        testcase_count=testcase_count,
                    )
                else:
                    tc_system = AUTO_GEN_TESTCASE_SYSTEM
                    tc_user = f"""请为以下题目生成 {testcase_count} 份模拟考生作答：

【题目】{qdata['content']}
【满分】{qdata.get('max_score', score)} 分
【标准答案】{qdata.get('standard_answer', '')}
【评分要点】{qdata.get('rubric_points', '无')}

请生成覆盖满分、中等、偏低、全错等不同梯度的作答。直接输出 JSON 数组。"""

                tc_resp = grading_engine.client.chat.completions.create(
                    model=grading_engine.model,
                    messages=[
                        {"role": "system", "content": tc_system},
                        {"role": "user", "content": tc_user}
                    ],
                    temperature=0.6,
                    max_tokens=4096,
                )
                tc_raw = tc_resp.choices[0].message.content.strip()
                cases = None
                try:
                    cases = json.loads(tc_raw)
                except json.JSONDecodeError:
                    m2 = re.search(r'\[[\s\S]*\]', tc_raw)
                    if m2:
                        cases = json.loads(m2.group())

                if cases and isinstance(cases, list):
                    for c in cases:
                        if c.get('answer_text') and c.get('expected_score') is not None:
                            add_test_case(
                                question_id=qid,
                                answer_text=c['answer_text'],
                                expected_score=float(c['expected_score']),
                                description=c.get('description', '模拟作答'),
                                case_type=c.get('case_type', 'simulated')
                            )
                            tc_saved += 1
            except Exception as e:
                logger.warning(f"生成测试用例失败: {e}")

            existing_titles.append(title)
            results.append({
                'question_id': qid,
                'title': title,
                'test_cases': tc_saved,
                'has_rubric_script': bool(rubric_script)
            })
            logger.info(f"自动出题 {i+1}/{count}: ID={qid}, 标题={title}, 用例={tc_saved}")

        except Exception as e:
            logger.error(f"自动出题第{i+1}道异常: {e}")
            continue

    return jsonify({
        'success': True,
        'data': {
            'subject': subject,
            'generated': len(results),
            'questions': results
        }
    })
