"""
数据库API路由 - 连接前端和数据库
"""
import json
from flask import Blueprint, request, jsonify
from loguru import logger
from app.models.db_models import (
    add_question, get_questions, get_question,
    update_question, delete_question,
    add_grading_record, get_grading_history,
    create_batch_task, update_batch_task, get_batch_task,
    get_syllabus, get_all_syllabus, upsert_syllabus, delete_syllabus,
    add_test_case, get_test_cases, get_test_case,
    update_test_case, delete_test_case, update_test_case_result
)
# 使用 Qwen-Agent 官方评分引擎替换原聚合引擎
from app.qwen_engine import QwenGradingEngine
from config.settings import GRADING_CONFIG

api_bp = Blueprint('api', __name__, url_prefix='/api')
grading_engine = QwenGradingEngine(GRADING_CONFIG)


# =============================================================================
# 评分脚本生成 Prompt
# =============================================================================

RUBRIC_SCRIPT_SYSTEM_PROMPT = """你是一位资深教育测评专家，擅长将评分规则转化为结构化的、无歧义的评分指令。

你的任务：根据提供的题目信息，生成一段【结构化评分脚本】。这段脚本将被保存并作为大模型自动阅卷时的**唯一评分依据**。评分时，阅卷模型只会看到这段脚本和考生答案，不会看到其他任何信息。

因此，评分脚本必须做到：
1. **完全自包含**：任何拿到脚本的人/模型，无需任何额外上下文就能准确评分
2. **跨系统一致**：不同机器、不同大模型（通义千问、智谱GLM、文心一言、豆包等）拿到同一脚本+同一答案，应给出相同分数
3. **容错性强**：能正确处理各种考生作答情况（完整答、部分答、用口语化表达、字很少、偏题、乱写等）

## 评分脚本的规范要求

### 1. 结构要求
评分脚本必须包含以下段落（按顺序）：

- 【题目信息】：完整复述题目内容和满分值（不要截断或省略）

- 【标准答案要点】：从标准答案中提炼出的核心要点，每个要点附带：
  - 要点的**核心含义**（用自己的话解释这个要点在说什么）
  - 要点的**关键词和表述方式**（考生可能怎么说）
  - 不要只列关键词，要把"为什么这是得分点"说清楚

- 【逐项评分规则】：每个得分点的判断标准，必须包含：
  - **得分条件**：什么情况下得满分，给出具体判断步骤（先检查什么，再检查什么）
  - **部分得分条件**：什么情况下得部分分，得多少，举例说明
  - **不得分条件**：什么情况下不得分
  - **易混淆判断**：哪些表述看起来相关但实际不应给分（防止误判）
  - 每个得分点必须列出【必含关键词】和【等价表述】

- 【作答情况分类】：预先定义几种典型作答模式及其评分方式，例如：
  - 完整作答：覆盖所有要点→满分
  - 部分作答：只覆盖部分要点→按覆盖情况给分
  - 空白/无关：没答或答非所问→0分
  - 字数很少但关键：虽然字少但命中关键词→按规则正常给分

- 【扣分规则】（如有）：明确的扣分条件和幅度；如无扣分则写"本题无额外扣分项"

- 【总分计算】：总分 = 各项得分之和 - 扣分项，总分范围 [0, 满分]

- 【输出格式要求】：强制指定 JSON 输出格式

### 2. 语言要求
- **绝对禁止**使用以下模糊表述："酌情给分"、"视情况"、"根据质量"、"适当给分"、"可能给分"、"一般而言"、"通常"、"较好地"、"基本正确"
- **必须使用**确定性表述："如果...则得X分"、"只要提到...即得X分"、"未提到...则0分"、"包含...关键词得X分"、"当且仅当...得X分"
- 每个得分点的分值必须明确，不能有范围值
- 部分得分必须指定具体分值（如"只答对其中一个方面得1分"），不能说"酌情给0.5-1分"

### 3. 一致性保障
- 每个得分点使用**关键词匹配 + 语义匹配**双重判断
- 列出每个得分点的【必含关键词】（用于快速判断）
- 列出每个得分点的【等价表述】（用于语义匹配，至少3个）
- 明确区分"必须同时满足"和"满足其一即可"的条件
- 对于有多个子要点的得分点，明确写出"两个子要点都答对得X分，只答对一个得Y分"
- **关键**：关键词匹配优先于语义匹配。如果考生答案包含关键词，即使整体表述不理想也应给分

### 4. 抗干扰能力
- 脚本必须能区分"答对了"和"沾了点边但没答对"
- 对于概念类题目，明确区分"说出了概念名称"和"解释了概念含义"（有些题目要求解释，不能只写名称）
- 对于列举类题目，明确写出"列举N个要点得X分"，并标注哪些算同一个要点（防止同义重复计分）

### 5. 输出格式
- 生成的评分脚本本身就是一段结构化文本，不要用代码/函数形式
- 直接输出评分脚本内容，不要加任何解释"""


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


@api_bp.route('/questions', methods=['GET'])
def list_questions():
    """获取题目列表"""
    subject = request.args.get('subject')
    questions = get_questions(subject)
    # 转换rubric字符串为对象
    for q in questions:
        if isinstance(q.get('rubric'), str):
            try:
                q['rubric'] = json.loads(q['rubric'])
            except:
                pass
    return jsonify({'success': True, 'data': questions})


@api_bp.route('/questions/<int:question_id>', methods=['GET'])
def get_question_detail(question_id):
    """获取题目详情"""
    question = get_question(question_id)
    if not question:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if isinstance(question.get('rubric'), str):
        try:
            question['rubric'] = json.loads(question['rubric'])
        except:
            pass
    return jsonify({'success': True, 'data': question})


@api_bp.route('/questions', methods=['POST'])
def create_question():
    """创建新题目"""
    data = request.json
    rubric = data.get('rubric')
    if isinstance(rubric, dict):
        rubric = json.dumps(rubric, ensure_ascii=False)

    question_id = add_question(
        subject=data.get('subject', 'general'),
        title=data.get('title', ''),
        content=data.get('content', ''),
        original_text=data.get('original_text'),
        standard_answer=data.get('standard_answer'),
        rubric_rules=data.get('rubric_rules'),
        rubric_points=data.get('rubric_points'),
        rubric_script=data.get('rubric_script'),
        rubric=rubric,
        max_score=data.get('max_score', 10.0),
        quality_score=data.get('quality_score')
    )
    return jsonify({'success': True, 'data': {'id': question_id}})


@api_bp.route('/questions/<int:question_id>', methods=['PUT'])
def update_question_detail(question_id):
    """更新题目"""
    data = request.json
    rubric = data.get('rubric')
    if isinstance(rubric, dict):
        rubric = json.dumps(rubric, ensure_ascii=False)
    if not rubric:
        # rubric 列 NOT NULL，缺失时保留原值
        existing = get_question(question_id)
        rubric = existing.get('rubric', '{}') if existing else '{}'

    success = update_question(
        question_id,
        subject=data.get('subject', 'general'),
        title=data.get('title', ''),
        content=data.get('content', ''),
        original_text=data.get('original_text'),
        standard_answer=data.get('standard_answer'),
        rubric_rules=data.get('rubric_rules'),
        rubric_points=data.get('rubric_points'),
        rubric_script=data.get('rubric_script'),
        rubric=rubric,
        max_score=data.get('max_score', 10.0),
        quality_score=data.get('quality_score')
    )
    if not success:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    return jsonify({'success': True, 'data': {'id': question_id}})


@api_bp.route('/questions/<int:question_id>', methods=['DELETE'])
def delete_question_detail(question_id):
    """删除题目"""
    success = delete_question(question_id)
    if not success:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    return jsonify({'success': True, 'data': {'id': question_id}})


import asyncio

@api_bp.route('/grade', methods=['POST'])
async def grade_answer():
    """评分答案 - 使用 Qwen-Agent GradingAgent"""
    data = request.json
    question_id = data.get('question_id') or data.get('questionId')
    student_answer = data.get('answer', '')

    # 如果传了 question_id，优先从数据库加载题目信息
    question_text = data.get('question', '')
    rubric = data.get('rubric', {})
    max_score = data.get('max_score', 10.0)

    if question_id:
        q = get_question(int(question_id))
        if q:
            question_text = q.get('content') or question_text
            max_score = q.get('max_score') or max_score
            # 将数据库字段注入 rubric 字典，供 _format_rubric 使用
            if not rubric:
                rubric = {}
            if q.get('rubric_script'):
                rubric['rubricScript'] = q['rubric_script']
            if q.get('rubric_rules'):
                rubric['rubricRules'] = q['rubric_rules']
            if q.get('rubric_points'):
                rubric['rubricPoints'] = q['rubric_points']
            if q.get('standard_answer'):
                rubric['standardAnswer'] = q['standard_answer']
            # 如果数据库里存了 JSON rubric，也合并进来
            if q.get('rubric'):
                try:
                    import json as _json
                    db_rubric = _json.loads(q['rubric']) if isinstance(q['rubric'], str) else q['rubric']
                    if isinstance(db_rubric, dict):
                        for k, v in db_rubric.items():
                            if k not in rubric or not rubric[k]:
                                rubric[k] = v
                except Exception:
                    pass

    # 使用 Qwen-Agent GradingAgent 评分
    result = await grading_engine.grade(
        question=question_text,
        answer=student_answer,
        rubric=rubric,
        max_score=max_score
    )

    # 边界检查
    result = grading_engine.boundary_check(result)

    # 保存评分记录
    record_id = add_grading_record(
        question_id=question_id,
        student_answer=student_answer,
        score=result.final_score,
        details=json.dumps(result.dict(), ensure_ascii=False),
        model_used='qwen-agent',
        confidence=result.confidence
    )

    return jsonify({
        'success': True,
        'data': {
            'record_id': record_id,
            'score': result.final_score,
            'confidence': result.confidence,
            'comment': result.comment,
            'details': result.dict(),
            'model_used': 'qwen-agent',
            'needs_review': result.needs_review,
            'warning': result.warning
        }
    })


@api_bp.route('/history', methods=['GET'])
def list_history():
    """获取评分历史"""
    question_id = request.args.get('question_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    history = get_grading_history(question_id, limit)
    # 转换details字符串为对象
    for h in history:
        if isinstance(h.get('details'), str):
            try:
                h['details'] = json.loads(h['details'])
            except:
                pass
    return jsonify({'success': True, 'data': history})


@api_bp.route('/batch', methods=['POST'])
async def create_batch():
    """创建批量评分任务 - 使用 Qwen-Agent GradingAgent"""
    data = request.json
    task_name = data.get('task_name', '批量评分')
    answers = data.get('answers', [])

    task_id = create_batch_task(task_name, len(answers))

    # 处理批量评分
    results = []
    for i, item in enumerate(answers):
        result = await grading_engine.grade(
            question=item.get('question', ''),
            answer=item.get('answer', ''),
            rubric=item.get('rubric', {}),
            max_score=item.get('max_score', 10.0)
        )
        results.append({
            'index': i,
            'score': result.final_score,
            'confidence': result.confidence,
            'comment': result.comment
        })
        update_batch_task(task_id, i + 1, json.dumps(results, ensure_ascii=False), 'running')

    update_batch_task(task_id, len(answers), json.dumps(results, ensure_ascii=False), 'completed')

    return jsonify({
        'success': True,
        'data': {
            'task_id': task_id,
            'results': results
        }
    })


@api_bp.route('/batch/<int:task_id>', methods=['GET'])
def get_batch_status(task_id):
    """获取批量任务状态"""
    task = get_batch_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    results = None
    if task.get('results'):
        try:
            results = json.loads(task['results'])
        except:
            pass

    return jsonify({
        'success': True,
        'data': {
            'task_id': task_id,
            'task_name': task.get('task_name'),
            'total_count': task.get('total_count'),
            'completed_count': task.get('completed_count'),
            'status': task.get('status'),
            'progress': round(task.get('completed_count', 0) / max(task.get('total_count', 1), 1) * 100, 1),
            'results': results
        }
    })


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    from app.models.db_models import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    # 总题目数
    cursor.execute('SELECT COUNT(*) FROM questions')
    total_questions = cursor.fetchone()[0]

    # 总评分次数
    cursor.execute('SELECT COUNT(*) FROM grading_records')
    total_gradings = cursor.fetchone()[0]

    # 平均分
    cursor.execute('SELECT AVG(score) FROM grading_records WHERE score IS NOT NULL')
    avg_score = cursor.fetchone()[0] or 0

    # 各科目题目数
    cursor.execute('SELECT subject, COUNT(*) FROM questions GROUP BY subject')
    subjects = dict(cursor.fetchall())

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'total_questions': total_questions,
            'total_gradings': total_gradings,
            'average_score': round(avg_score, 2),
            'subjects': subjects
        }
    })


@api_bp.route('/generate-rubric-script', methods=['POST'])
def generate_rubric_script():
    """AI 生成结构化评分脚本"""
    data = request.json
    content = data.get('content', '').strip()
    score = data.get('score', 10)
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_rules = data.get('rubricRules', '').strip()
    rubric_points = data.get('rubricPoints', '').strip()
    ai_rubric = data.get('aiRubric', '').strip()

    if not content:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空，请先填写标准答案'}), 400

    # 构建用户提示词
    user_prompt = f"""请根据以下信息生成结构化评分脚本：

【题目内容】
{content}

【满分】
{score} 分

【标准答案】
{standard_answer}"""

    if rubric_rules:
        user_prompt += f"\n\n【评分规则】\n{rubric_rules}"
    if rubric_points:
        user_prompt += f"\n\n【分数分布/得分要点】\n{rubric_points}"
    if ai_rubric:
        user_prompt += f"\n\n【评分提示词/补充说明】\n{ai_rubric}"

    user_prompt += """

请生成结构化评分脚本，确保：
1. 自包含所有评分信息，无需额外上下文
2. 逐项检查、逐项给分，每项分值明确
3. 使用确定性语言，无模糊表述
4. 包含关键词和等价表述辅助判断
5. 指定 JSON 输出格式：{"总分": X, "评语": "..."}
6. 直接输出评分脚本内容，不要加任何解释"""

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": RUBRIC_SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        rubric_script = response.choices[0].message.content.strip()

        if not rubric_script or len(rubric_script) < 50:
            return jsonify({'success': False, 'error': 'AI 生成的评分脚本内容过短，请重试'}), 500

        logger.info(f"评分脚本生成成功，长度: {len(rubric_script)} 字符")
        return jsonify({'success': True, 'data': {'rubricScript': rubric_script}})
    except Exception as e:
        logger.error(f"生成评分脚本失败：{e}")
        return jsonify({'success': False, 'error': f'生成失败：{str(e)}'}), 500


@api_bp.route('/evaluate-question', methods=['POST'])
def evaluate_question():
    """AI 命题质量评估"""
    import re
    data = request.json
    content = data.get('content', '').strip()
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_points = data.get('rubricPoints', '').strip()
    rubric_rules = data.get('rubricRules', '').strip()
    max_score = data.get('maxScore', 10)
    difficulty = data.get('difficulty', '')
    content_type = data.get('contentType', '')

    if not content:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空，无法评估质量'}), 400

    user_prompt = f"""请评估以下命题的质量：

【题目内容】
{content}

【满分】
{max_score} 分

【标准答案】
{standard_answer}"""

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

    fallback_result = {
        'overall_score': 50,
        'verdict': 'warning',
        'issues': [{'category': '整体', 'severity': 'warning', 'description': 'AI 评估未能返回有效结果，请人工检查'}],
        'suggestions': ['建议人工审核题目质量']
    }

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": QUALITY_EVALUATION_SYSTEM_PROMPT},
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


# =============================================================================
# 考试大纲 / 教材内容 API
# =============================================================================

@api_bp.route('/syllabus', methods=['GET'])
def list_syllabus():
    """获取大纲/教材列表，可按科目筛选"""
    subject = request.args.get('subject')
    items = get_all_syllabus(subject)
    return jsonify({'success': True, 'data': items})


@api_bp.route('/syllabus/<subject>/<content_type>', methods=['GET'])
def get_syllabus_detail(subject, content_type):
    """获取某科目某类型的大纲/教材内容"""
    item = get_syllabus(subject, content_type)
    if not item:
        return jsonify({'success': True, 'data': {'subject': subject, 'content_type': content_type, 'title': '', 'content': ''}})
    return jsonify({'success': True, 'data': item})


@api_bp.route('/syllabus', methods=['POST'])
def save_syllabus():
    """保存（新增或更新）大纲/教材内容"""
    data = request.json
    subject = data.get('subject', '').strip()
    content_type = data.get('content_type', '').strip()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not subject:
        return jsonify({'success': False, 'error': '科目不能为空'}), 400
    if content_type not in ('syllabus', 'textbook'):
        return jsonify({'success': False, 'error': '内容类型必须是 syllabus 或 textbook'}), 400

    row_id = upsert_syllabus(subject, content_type, title, content)
    logger.info(f"大纲/教材已保存: subject={subject}, type={content_type}, id={row_id}")
    return jsonify({'success': True, 'data': {'id': row_id}})


@api_bp.route('/syllabus/<subject>/<content_type>', methods=['DELETE'])
def remove_syllabus(subject, content_type):
    """删除大纲/教材内容"""
    success = delete_syllabus(subject, content_type)
    if not success:
        return jsonify({'success': False, 'error': '内容不存在'}), 404
    return jsonify({'success': True})


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
    return jsonify({'success': True, 'data': {'id': row_id}})


@api_bp.route('/questions/<int:question_id>/test-cases/<int:test_case_id>', methods=['PUT'])
def update_test_case_detail(question_id, test_case_id):
    """更新测试用例"""
    data = request.json
    tc = get_test_case(test_case_id)
    if not tc or tc['question_id'] != question_id:
        return jsonify({'success': False, 'error': '测试用例不存在'}), 404

    success = update_test_case(
        test_case_id,
        answer_text=data.get('answer_text', tc['answer_text']),
        expected_score=float(data.get('expected_score', tc['expected_score'])),
        description=data.get('description', tc['description']),
        case_type=data.get('case_type', tc['case_type'])
    )
    return jsonify({'success': True, 'data': {'id': test_case_id}})


@api_bp.route('/questions/<int:question_id>/test-cases/<int:test_case_id>', methods=['DELETE'])
def delete_test_case_detail(question_id, test_case_id):
    """删除测试用例"""
    tc = get_test_case(test_case_id)
    if not tc or tc['question_id'] != question_id:
        return jsonify({'success': False, 'error': '测试用例不存在'}), 404
    delete_test_case(test_case_id)
    return jsonify({'success': True})


# =============================================================================
# 评分脚本验证
# =============================================================================

@api_bp.route('/verify-rubric', methods=['POST'])
async def verify_rubric():
    """验证评分脚本：对所有测试用例运行评分，对比实际分与期望分"""
    data = request.json
    question_id = data.get('question_id')
    tolerance = float(data.get('tolerance', 1.0))

    if not question_id:
        return jsonify({'success': False, 'error': 'question_id 不能为空'}), 400

    # 加载题目
    q = get_question(int(question_id))
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404

    # 加载测试用例
    cases = get_test_cases(int(question_id))
    if not cases:
        return jsonify({'success': False, 'error': '该题目没有测试用例，请先添加'}), 400

    # 构建 rubric 字典
    rubric = {}
    rubric_script = data.get('rubric_script', '').strip()
    if rubric_script:
        rubric['rubricScript'] = rubric_script
    elif q.get('rubric_script'):
        rubric['rubricScript'] = q['rubric_script']
    if q.get('rubric_rules'):
        rubric['rubricRules'] = q['rubric_rules']
    if q.get('rubric_points'):
        rubric['rubricPoints'] = q['rubric_points']
    if q.get('standard_answer'):
        rubric['standardAnswer'] = q['standard_answer']
    # 合并 rubric JSON
    if q.get('rubric'):
        try:
            db_rubric = json.loads(q['rubric']) if isinstance(q['rubric'], str) else q['rubric']
            if isinstance(db_rubric, dict):
                for k, v in db_rubric.items():
                    if k not in rubric or not rubric[k]:
                        rubric[k] = v
        except Exception:
            pass

    question_text = q.get('content', '')
    max_score = q.get('max_score', 10.0)

    # 逐个评分
    results = []
    for tc in cases:
        try:
            result = await grading_engine.grade(
                question=question_text,
                answer=tc['answer_text'],
                rubric=rubric,
                max_score=max_score
            )
            actual_score = result.final_score
            error = abs(actual_score - tc['expected_score'])
            passed = error <= tolerance

            # 更新数据库
            update_test_case_result(tc['id'], actual_score, error)

            results.append({
                'test_case_id': tc['id'],
                'description': tc['description'],
                'case_type': tc['case_type'],
                'answer_text': tc['answer_text'][:100],
                'expected_score': tc['expected_score'],
                'actual_score': actual_score,
                'error': round(error, 2),
                'passed': passed,
                'confidence': result.confidence,
                'comment': result.comment[:200] if result.comment else ''
            })
        except Exception as e:
            logger.error(f"验证用例 {tc['id']} 失败: {e}")
            results.append({
                'test_case_id': tc['id'],
                'description': tc['description'],
                'case_type': tc['case_type'],
                'answer_text': tc['answer_text'][:100],
                'expected_score': tc['expected_score'],
                'actual_score': None,
                'error': None,
                'passed': False,
                'confidence': 0,
                'comment': f'评分失败: {str(e)}'
            })

    # 计算统计
    valid_results = [r for r in results if r['actual_score'] is not None]
    passed_count = sum(1 for r in valid_results if r['passed'])
    errors = [r['error'] for r in valid_results]

    return jsonify({
        'success': True,
        'data': {
            'question_id': question_id,
            'total_cases': len(results),
            'passed_cases': passed_count,
            'accuracy': round(passed_count / len(valid_results) * 100, 1) if valid_results else 0,
            'mean_absolute_error': round(sum(errors) / len(errors), 2) if errors else 0,
            'max_absolute_error': round(max(errors), 2) if errors else 0,
            'tolerance': tolerance,
            'results': results
        }
    })


# =============================================================================
# AI 自动出题
# =============================================================================

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
        "case_type": "simulated",
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


@api_bp.route('/auto-generate', methods=['POST'])
def auto_generate():
    """AI 自动出题 + 评分脚本 + 测试用例"""
    import re as _re
    import random
    data = request.json or {}
    subject = data.get('subject', 'politics')
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
                    {"role": "system", "content": AUTO_GEN_QUESTION_SYSTEM},
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
                m = _re.search(r'\{[\s\S]*\}', raw)
                if m:
                    qdata = json.loads(m.group())

            if not qdata or not qdata.get('content'):
                logger.warning(f"自动出题第{i+1}道：解析失败")
                continue

            # 生成评分脚本
            rubric_script = None
            try:
                rs_resp = grading_engine.client.chat.completions.create(
                    model=grading_engine.model,
                    messages=[
                        {"role": "system", "content": RUBRIC_SCRIPT_SYSTEM_PROMPT},
                        {"role": "user", "content": f"""请根据以下信息生成结构化评分脚本：

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

请直接输出评分脚本，不要任何解释。"""}
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
                tc_resp = grading_engine.client.chat.completions.create(
                    model=grading_engine.model,
                    messages=[
                        {"role": "system", "content": AUTO_GEN_TESTCASE_SYSTEM},
                        {"role": "user", "content": f"""请为以下题目生成 {testcase_count} 份模拟考生作答：

【题目】{qdata['content']}
【满分】{qdata.get('max_score', score)} 分
【标准答案】{qdata.get('standard_answer', '')}
【评分要点】{qdata.get('rubric_points', '无')}

请生成覆盖满分、中等、偏低、全错等不同梯度的作答。直接输出 JSON 数组。"""}
                    ],
                    temperature=0.6,
                    max_tokens=4096,
                )
                tc_raw = tc_resp.choices[0].message.content.strip()
                cases = None
                try:
                    cases = json.loads(tc_raw)
                except json.JSONDecodeError:
                    m2 = _re.search(r'\[[\s\S]*\]', tc_raw)
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
