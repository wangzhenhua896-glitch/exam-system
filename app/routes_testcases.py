"""
考试大纲 / 教材 / 测试用例管理 / 生成测试用例
"""
import json
import re
from flask import request, jsonify, session
from loguru import logger
from app.api_shared import (
    api_bp, grading_engine, _check_subject_access, _session_subject,
)
from app.models.db_models import (
    get_question,
    get_syllabus, get_all_syllabus, upsert_syllabus, delete_syllabus,
    add_test_case, get_test_cases, get_test_case,
    update_test_case, delete_test_case, update_test_case_result,
    get_all_test_cases_overview, get_all_test_cases_with_question,
    save_script_version,
)
from app.english_prompts import (
    STYLE_GUIDE_EN,
)


# =============================================================================
# 考试大纲 / 教材内容 API
# =============================================================================

@api_bp.route('/syllabus', methods=['GET'])
def list_syllabus():
    """获取大纲/教材列表 — 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject() or request.args.get('subject')
    items = get_all_syllabus(subject)
    return jsonify({'success': True, 'data': items})


@api_bp.route('/syllabus/<subject>/<content_type>', methods=['GET'])
def get_syllabus_detail(subject, content_type):
    """获取某科目某类型的大纲/教材内容"""
    if not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权访问其他科目的大纲'}), 403
    item = get_syllabus(subject, content_type)
    if not item:
        return jsonify({'success': True, 'data': {'subject': subject, 'content_type': content_type, 'title': '', 'content': ''}})
    return jsonify({'success': True, 'data': item})


@api_bp.route('/syllabus', methods=['POST'])
def save_syllabus():
    """保存（新增或更新）大纲/教材内容 — 非 admin 强制 subject = session.subject"""
    data = request.json
    subject = data.get('subject', '').strip()
    content_type = data.get('content_type', '').strip()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not subject:
        return jsonify({'success': False, 'error': '科目不能为空'}), 400
    if content_type not in ('syllabus', 'textbook'):
        return jsonify({'success': False, 'error': '内容类型必须是 syllabus 或 textbook'}), 400
    if not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权修改其他科目的大纲'}), 403

    row_id = upsert_syllabus(subject, content_type, title, content)
    logger.info(f"大纲/教材已保存: subject={subject}, type={content_type}, id={row_id}")
    return jsonify({'success': True, 'data': {'id': row_id}})


@api_bp.route('/syllabus/<subject>/<content_type>', methods=['DELETE'])
def remove_syllabus(subject, content_type):
    """删除大纲/教材内容"""
    if not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权删除其他科目的大纲'}), 403
    success = delete_syllabus(subject, content_type)
    if not success:
        return jsonify({'success': False, 'error': '内容不存在'}), 404
    return jsonify({'success': True})


# =============================================================================
# 测试集管理（独立页面）
# =============================================================================

@api_bp.route('/test-cases/overview', methods=['GET'])
def test_cases_overview():
    """获取所有题目的测试用例统计概览 — 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject() or request.args.get('subject')
    data = get_all_test_cases_overview(subject)
    return jsonify({'success': True, 'data': data})


@api_bp.route('/test-cases/all', methods=['GET'])
def test_cases_all():
    """获取所有测试用例（含题目信息）— 非 admin 强制用 session.subject 过滤"""
    subject = _session_subject() or request.args.get('subject')
    data = get_all_test_cases_with_question(subject)
    return jsonify({'success': True, 'data': data})


# =============================================================================
# 测试用例 CRUD
# =============================================================================

@api_bp.route('/questions/<int:question_id>/test-cases', methods=['GET'])
def list_test_cases(question_id):
    """获取某题目的所有测试用例"""
    cases = get_test_cases(question_id)
    return jsonify({'success': True, 'data': cases})


@api_bp.route('/questions/<int:question_id>/test-cases', methods=['POST'])
def create_test_case(question_id):
    """添加测试用例"""
    # 科目访问控制
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权操作其他科目的测试用例'}), 403

    data = request.json
    answer_text = data.get('answer_text', '').strip()
    expected_score = data.get('expected_score')
    if not answer_text:
        return jsonify({'success': False, 'error': '答案内容不能为空'}), 400
    if expected_score is None:
        return jsonify({'success': False, 'error': '期望分数不能为空'}), 400

    row_id = add_test_case(
        question_id=question_id,
        answer_text=answer_text,
        expected_score=float(expected_score),
        description=data.get('description', ''),
        case_type=data.get('case_type', 'simulated')
    )

    # 场景联动：新增场景后，在版本历史中记录
    try:
        q = get_question(question_id)
        if q and q.get('rubric_script'):
            total = len(get_test_cases(question_id))
            save_script_version(
                question_id, q['rubric_script'],
                note=f'新增场景（当前共{total}个场景）',
            )
    except Exception as e:
        logger.warning(f"新增场景联动版本历史失败: {e}")

    return jsonify({'success': True, 'data': {'id': row_id}})


@api_bp.route('/questions/<int:question_id>/test-cases/<int:test_case_id>', methods=['PUT'])
def update_test_case_detail(question_id, test_case_id):
    """更新测试用例"""
    data = request.json
    tc = get_test_case(test_case_id)
    if not tc or tc['question_id'] != question_id:
        return jsonify({'success': False, 'error': '测试用例不存在'}), 404
    # 科目访问控制
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的测试用例'}), 403

    success = update_test_case(
        test_case_id,
        answer_text=data.get('answer_text', tc['answer_text']),
        expected_score=float(data.get('expected_score', tc['expected_score'])),
        description=data.get('description', tc['description']),
        case_type=data.get('case_type', tc['case_type'])
    )

    # 支持回写评分结果
    if 'last_actual_score' in data and 'last_error' in data:
        update_test_case_result(
            test_case_id,
            actual_score=float(data['last_actual_score']),
            error=float(data['last_error'])
        )
    return jsonify({'success': True, 'data': {'id': test_case_id}})


@api_bp.route('/questions/<int:question_id>/test-cases/<int:test_case_id>', methods=['DELETE'])
def delete_test_case_detail(question_id, test_case_id):
    """删除测试用例"""
    tc = get_test_case(test_case_id)
    if not tc or tc['question_id'] != question_id:
        return jsonify({'success': False, 'error': '测试用例不存在'}), 404
    # 科目访问控制
    q = get_question(question_id)
    if q and not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权删除其他科目的测试用例'}), 403
    delete_test_case(test_case_id)
    return jsonify({'success': True})


@api_bp.route('/questions/<int:question_id>/generate-test-cases', methods=['POST'])
def generate_test_cases_for_question(question_id):
    """为已有题目自动生成测试用例（支持参数化配置）"""
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权操作其他科目的题目'}), 403

    data = request.json or {}
    count = int(data.get('count', 7))
    distribution = data.get('distribution', 'gradient')  # gradient / edge / middle / uniform
    styles = data.get('styles', ['标准规范', '口语化', '要点遗漏'])
    extra = data.get('extra', '').strip()

    # 构建题目数据
    question_data = {
        'content': q.get('content', ''),
        'max_score': q.get('max_score', 10),
        'standard_answer': q.get('standard_answer', ''),
        'rubric_points': q.get('rubric_points', ''),
        'rubric_script': q.get('rubric_script', ''),
        'rubric_rules': q.get('rubric_rules', ''),
        'subject': q.get('subject', 'general'),
    }

    if not question_data['content']:
        return jsonify({'success': False, 'error': '题目内容为空'}), 400

    # 使用评分引擎的 client
    client = grading_engine.client
    model = grading_engine.model

    max_score = question_data['max_score']

    # 分数分布描述
    dist_desc = {
        'gradient': f'梯度分布：{max_score}分、{round(max_score*0.75,1)}分、{round(max_score*0.5,1)}分、{round(max_score*0.35,1)}分、{round(max_score*0.15,1)}分、0分 均匀覆盖',
        'edge': f'边界为主：重点在 {max_score}分（满分）、{round(max_score*0.5,1)}分（及格线附近）、0分（零分）附近密集分布，临界分值仔细覆盖',
        'middle': f'中段为主：重点在 {round(max_score*0.4,1)}~{round(max_score*0.8,1)}分区间密集分布，少量满分和零分',
        'uniform': f'均匀分布：从0到{max_score}分，每个分数段数量相等',
    }

    # 作答风格详细描述（按科目区分）
    is_english = question_data.get('subject') == 'english'
    if is_english:
        style_guide = STYLE_GUIDE_EN
    else:
        style_guide = {
            '标准规范': '使用标准书面语，逻辑清晰，要点齐全，像优秀学生答卷',
            '口语化': '使用口语化表达，句子不完整，有错别字或语病，但核心意思到了',
            '要点遗漏': '部分内容答对但遗漏了关键要点，导致部分失分',
            '偏题跑题': '没有理解题意，答非所问，内容与题目无关或严重偏离',
            '复制原文': '照抄题目原文或标准答案原文（用于测试反作弊规则）',
            '空白作答': '空白、只写"不知道"、或写与题目完全无关的内容',
        }

    style_instructions = []
    for s in styles:
        desc = style_guide.get(s, s)
        style_instructions.append(f'- {s}：{desc}')

    # Prompt
    system_prompt = f"""你是一位经验丰富的阅卷老师，熟悉各类考生作答模式。

你的任务：根据题目和标准答案，生成 {count} 份模拟考生作答。

严格要求：
1. 每份作答必须像真实考生写的——有合理的对错、表达习惯和写作水平差异
2. expected_score 必须是根据评分标准可以明确给出的分数，不能有争议
3. 分数分布按以下策略：{dist_desc.get(distribution, dist_desc['gradient'])}
4. 作答风格覆盖以下类型：
{chr(10).join(style_instructions)}
5. 每份作答必须有明显的差异——不要出现两份内容相似的作答
6. 如果提供了【已有测试用例】区块，新生成的作答必须与每一条已有用例都明显不同：
   - 不同的表述方式（不能只是换同义词）
   - 不同的得分点组合（已有满分的，生成一个漏了关键点的）
   - 不同的错误模式（已有遗漏要点的，生成一个偏题的）
   - 不同的详细程度（已有详细的，生成一个简略的）
7. 如果包含"复制原文"风格，确保作答是照抄题目或标准答案（用于触发反作弊）
8. 如果包含"口语化"风格，要模拟真实口语表达习惯，有语气词、断句、错别字等

输出格式（严格 JSON 数组）：
[
    {{
        "description": "简短描述（如：满分作答、要点不全、完全偏题）",
        "case_type": "ai_generated",
        "answer_text": "模拟的考生作答内容",
        "expected_score": 期望分数
    }}
]

注意：
- expected_score 必须是具体数字，不能是范围
- 每份作答的 answer_text 要足够长且真实（不能只写一句话）
- 不要输出任何 JSON 以外的内容"""

    rubric_parts = []
    if question_data.get('rubric_script'):
        rubric_parts.append(f"【评分脚本】\n{question_data['rubric_script']}")
    if question_data.get('rubric_rules'):
        rubric_parts.append(f"【评分规则】\n{question_data['rubric_rules']}")
    if question_data.get('rubric_points'):
        rubric_parts.append(f"【评分要点】\n{question_data['rubric_points']}")

    rubric_text = '\n\n'.join(rubric_parts) if rubric_parts else '无'

    # 已有测试用例（用于去重提示）
    existing_cases = get_test_cases(question_id)
    existing_block = ''
    if existing_cases:
        existing_lines = []
        for i, ec in enumerate(existing_cases, 1):
            snippet = ec['answer_text'][:80].replace('\n', ' ')
            existing_lines.append(f"{i}. [期望{ec['expected_score']}分] {snippet}...")
        existing_block = f"""

【已有测试用例（共{len(existing_cases)}条，新生成的必须与以下内容明显不同）】
{chr(10).join(existing_lines)}"""

    user_prompt = f"""请为以下题目生成 {count} 份模拟考生作答：

【题目】
{question_data['content']}

【满分】
{max_score} 分

【标准答案】
{question_data['standard_answer']}

{rubric_text}

【分数分布】
{dist_desc.get(distribution, dist_desc['gradient'])}

【要求覆盖的作答风格】
{chr(10).join(style_instructions)}{existing_block}"""

    if extra:
        user_prompt += f"\n\n【补充要求】\n{extra}"

    user_prompt += "\n\n直接输出 JSON 数组，不要任何解释。"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4096,
            stream=False,
        )
        raw = response.choices[0].message.content.strip()

        # 解析 JSON
        cases = None
        try:
            cases = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\[[\s\S]*\]', raw)
            if match:
                try:
                    cases = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if not cases or not isinstance(cases, list):
            return jsonify({'success': False, 'error': 'AI 返回格式无法解析', 'raw': raw[:200]}), 500

        # 保存测试用例
        saved = []
        for c in cases:
            if not c.get('answer_text') or c.get('expected_score') is None:
                continue
            row_id = add_test_case(
                question_id=question_id,
                answer_text=c['answer_text'],
                expected_score=float(c['expected_score']),
                description=c.get('description', '模拟作答'),
                case_type=c.get('case_type', 'simulated')
            )
            saved.append({'id': row_id, 'description': c.get('description', ''), 'expected_score': float(c['expected_score'])})

        # 场景联动：批量新增场景后，在版本历史中记录
        if saved:
            try:
                q_latest = get_question(question_id)
                if q_latest and q_latest.get('rubric_script'):
                    total = len(get_test_cases(question_id))
                    save_script_version(
                        question_id, q_latest['rubric_script'],
                        note=f'批量新增{len(saved)}个场景（当前共{total}个场景）',
                    )
            except Exception as e:
                logger.warning(f"批量新增场景联动版本历史失败: {e}")

        return jsonify({'success': True, 'data': {'count': len(saved), 'cases': saved}})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]}), 500
