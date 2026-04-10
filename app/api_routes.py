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
    update_test_case, delete_test_case, update_test_case_result,
    get_all_test_cases_overview, get_all_test_cases_with_question,
    save_script_version, get_script_history, get_script_version,
    check_sensitive_words,
    get_previous_grade,
    update_script_version_result,
    get_sensitive_words, add_sensitive_word, update_sensitive_word,
    delete_sensitive_word, batch_add_sensitive_words,
    get_users, get_user, add_user as db_add_user, update_user, delete_user,
    log_bug
)
# 使用 Qwen-Agent 官方评分引擎替换原聚合引擎
from app.qwen_engine import QwenGradingEngine
from app.models.registry import model_registry
from config.settings import GRADING_CONFIG

api_bp = Blueprint('api', __name__, url_prefix='/api')
grading_engine = QwenGradingEngine(GRADING_CONFIG)


PROVIDER_NAMES = {
    'qwen': '通义千问',
    'glm': '智谱 GLM',
    'ernie': '文心一言',
    'doubao': '豆包',
    'xiaomi_mimimo': '小米 Mimimo',
    'minimax': 'MiniMax',
    'spark': '讯飞星火',
}


@api_bp.route('/providers', methods=['GET'])
def list_enabled_providers():
    """列出所有已启用的 provider 及其子模型，供前端选择"""
    from app.models.db_models import get_effective_config
    providers = []
    for pid in ('qwen', 'glm', 'ernie', 'doubao', 'xiaomi_mimimo', 'minimax', 'spark'):
        cfg = get_effective_config(pid)
        if cfg.get("enabled") and cfg.get("api_key"):
            available = cfg.get("available_models", [])
            enabled_models = set(cfg.get("extra_config", {}).get("enabled_models", []))
            # 未设置过 enabled_models 时，所有模型默认可用
            all_enabled = not enabled_models
            if available:
                for m in available:
                    # 子模型是否被用户启用：在 enabled_models 列表中，或列表为空（全部默认可用）
                    is_enabled = all_enabled or m["id"] in enabled_models
                    is_selected = pid == getattr(grading_engine, '_selected_provider', '') and m["id"] == getattr(grading_engine, 'model', '')
                    providers.append({
                        "id": pid + '/' + m["id"],
                        "provider": pid,
                        "model": m["id"],
                        "name": PROVIDER_NAMES.get(pid, pid),
                        "display_name": m.get("name", m["id"]),
                        "active": is_enabled,
                        "selected": is_selected,
                    })
            else:
                providers.append({
                    "id": pid + '/' + cfg.get("model", ""),
                    "provider": pid,
                    "model": cfg.get("model", ""),
                    "name": PROVIDER_NAMES.get(pid, pid),
                    "display_name": cfg.get("model", ""),
                    "active": False,
                })
    return jsonify({"success": True, "data": providers})


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
    # 添加评分脚本版本信息
    history = get_script_history(question_id)
    question['script_version'] = history[0]['version'] if history else 0
    question['script_version_count'] = len(history)
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


@api_bp.route('/export-rubric-scripts', methods=['GET'])
def export_rubric_scripts():
    """按科目导出评分脚本，生成 Markdown 格式"""
    from flask import Response
    subject = request.args.get('subject', '').strip()
    if not subject:
        return jsonify({'success': False, 'error': '请指定科目参数'}), 400
    questions = get_questions(subject)

    # 过滤有评分脚本的题目
    questions_with_script = [q for q in questions if (q.get('rubric_script') or '').strip()]
    if not questions_with_script:
        return jsonify({'success': False, 'error': '没有找到包含评分脚本的题目'}), 404

    # 按科目分组
    grouped = {}
    for q in questions_with_script:
        subj = q.get('subject', '未分类')
        grouped.setdefault(subj, []).append(q)

    # 生成 Markdown
    lines = []
    lines.append('# 评分脚本导出')
    lines.append('')
    lines.append(f'> 导出时间：{__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'> 共 {len(questions_with_script)} 道题')
    lines.append('')
    lines.append('---')
    lines.append('')

    for subj, qs in grouped.items():
        # 科目标题
        subject_labels = {
            'politics': '思想政治', 'chinese': '语文', 'english': '英语',
            'math': '数学', 'history': '历史', 'geography': '地理',
            'physics': '物理', 'chemistry': '化学', 'biology': '生物',
        }
        label = subject_labels.get(subj, subj)
        lines.append(f'## {label}')
        lines.append('')

        for q in qs:
            title = q.get('title') or q.get('content', '')[:30]
            max_score = q.get('max_score', '?')
            lines.append(f'### {title}（{max_score}分）')
            lines.append('')

            # 题目内容
            content = q.get('content', '').strip()
            if content:
                lines.append('**题目：**')
                lines.append('')
                lines.append(content)
                lines.append('')

            # 标准答案
            standard_answer = q.get('standard_answer', '').strip()
            if standard_answer:
                lines.append('**标准答案：**')
                lines.append('')
                lines.append(standard_answer)
                lines.append('')

            # 评分脚本
            rubric_script = q.get('rubric_script', '').strip()
            if rubric_script:
                lines.append('**评分脚本：**')
                lines.append('')
                lines.append(rubric_script)
                lines.append('')

            lines.append('---')
            lines.append('')

    md_content = '\n'.join(lines)

    # 确定文件名（中文需 URL 编码，避免 latin-1 header 报错）
    from urllib.parse import quote
    filename = f'评分脚本_{subject}.md'
    filename_encoded = quote(filename)

    return Response(
        md_content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{filename_encoded}",
            'Content-Type': 'text/markdown; charset=utf-8',
        }
    )


@api_bp.route('/import-questions', methods=['POST'])
def import_questions():
    """从 Excel 导入题目"""
    import pandas as pd

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未上传文件'}), 400

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        return jsonify({'success': False, 'error': '仅支持 .xlsx/.xls/.csv 文件'}), 400

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return jsonify({'success': False, 'error': f'读取文件失败：{str(e)}'}), 400

    # 标准化列名（支持中英文）
    col_map = {}
    for col in df.columns:
        cl = str(col).strip().lower()
        if cl in ('科目', 'subject'):
            col_map['subject'] = col
        elif cl in ('标题', 'title', '题目标题'):
            col_map['title'] = col
        elif cl in ('题目', '题目内容', 'content', 'question'):
            col_map['content'] = col
        elif cl in ('标准答案', '答案', 'standard_answer', 'answer'):
            col_map['standard_answer'] = col
        elif cl in ('满分', 'max_score', 'score', '分值'):
            col_map['max_score'] = col
        elif cl in ('得分点', '评分要点', 'rubric_points', 'points'):
            col_map['rubric_points'] = col
        elif cl in ('评分规则', 'rubric_rules', 'rules'):
            col_map['rubric_rules'] = col

    if 'content' not in col_map:
        return jsonify({'success': False, 'error': '未找到「题目/题目内容/content」列，请检查表头'}), 400

    subject = request.form.get('subject', 'politics')
    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        content = str(row.get(col_map['content'], '')).strip()
        if not content or content == 'nan':
            skipped += 1
            continue

        title = str(row.get(col_map.get('title', ''), '')).strip()
        if title == 'nan':
            title = ''
        if not title:
            title = content[:30]

        standard_answer = str(row.get(col_map.get('standard_answer', ''), '')).strip()
        if standard_answer == 'nan':
            standard_answer = ''

        max_score_val = row.get(col_map.get('max_score', ''), 10)
        try:
            max_score_val = float(max_score_val) if max_score_val and str(max_score_val) != 'nan' else 10.0
        except:
            max_score_val = 10.0

        row_subject = str(row.get(col_map.get('subject', ''), subject)).strip()
        if row_subject == 'nan' or not row_subject:
            row_subject = subject

        rubric_points = str(row.get(col_map.get('rubric_points', ''), '')).strip()
        if rubric_points == 'nan':
            rubric_points = ''
        rubric_rules = str(row.get(col_map.get('rubric_rules', ''), '')).strip()
        if rubric_rules == 'nan':
            rubric_rules = ''

        rubric = json.dumps({
            'contentType': '简答题',
            'points': [],
        }, ensure_ascii=False)

        add_question(
            subject=row_subject,
            title=title,
            content=content,
            original_text=content,
            standard_answer=standard_answer,
            rubric_rules=rubric_rules,
            rubric_points=rubric_points,
            rubric_script='',
            rubric=rubric,
            max_score=max_score_val
        )
        imported += 1

    return jsonify({'success': True, 'data': {'imported': imported, 'skipped': skipped}})


import asyncio

@api_bp.route('/grade', methods=['POST'])
async def grade_answer():
    """评分答案 - 使用 Qwen-Agent GradingAgent"""
    data = request.json
    question_id = data.get('question_id') or data.get('questionId')
    student_answer = data.get('answer', '')
    student_id = data.get('student_id', '')

    # 空答案前置拦截：去除空格和标点后长度 < 2，直接0分，不调LLM
    import re as _re
    stripped = _re.sub(r'[\s\W]+', '', student_answer)
    if len(stripped) < 2:
        max_score = data.get('max_score', 10.0)
        if question_id:
            q = get_question(int(question_id))
            if q:
                max_score = q.get('max_score') or max_score
        record_id = add_grading_record(
            question_id=question_id,
            student_answer=student_answer,
            score=0,
            details=json.dumps({
                "final_score": 0,
                "comment": "考生未作答",
                "scoring_items": [],
                "needs_review": False,
                "warning": "答案为空或仅含标点，系统直接判0分"
            }, ensure_ascii=False),
            model_used='precheck',
            confidence=1.0,
            student_id=student_id or None
        )
        return jsonify({
            'success': True,
            'data': {
                'record_id': record_id,
                'score': 0,
                'confidence': 1.0,
                'comment': '考生未作答',
                'details': {
                    'final_score': 0,
                    'comment': '考生未作答',
                    'scoring_items': [],
                    'needs_review': False,
                    'warning': '答案为空或仅含标点，系统直接判0分'
                },
                'model_used': 'precheck',
                'needs_review': False,
                'warning': '答案为空或仅含标点，系统直接判0分'
            }
        })

    # 支持前端指定 provider 和 model
    provider = data.get('provider')
    model = data.get('model')
    if provider:
        grading_engine.set_provider(provider, model)

    # 如果传了 question_id，优先从数据库加载题目信息
    question_text = data.get('question', '')
    rubric = data.get('rubric', {})
    max_score = data.get('max_score', 10.0)
    subject = data.get('subject', 'general')

    if question_id:
        q = get_question(int(question_id))
        if q:
            question_text = q.get('content') or question_text
            max_score = q.get('max_score') or max_score
            if q.get('subject'):
                subject = q['subject']
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

    # 敏感词扫描
    sensitive_hits = check_sensitive_words(student_answer, subject)
    high_hits = [h for h in sensitive_hits if h.get('severity') == 'high']
    if high_hits:
        hit_words = '、'.join(h['word'] for h in high_hits)
        log_bug(
            bug_type='sensitive_word',
            description=f'答案触发敏感词：{hit_words}',
            details=json.dumps([h.get('word','') for h in high_hits], ensure_ascii=False),
            question_id=question_id,
            model_used='sensitive_filter'
        )
        record_id = add_grading_record(
            question_id=question_id,
            student_answer=student_answer,
            score=0,
            details=json.dumps({
                "final_score": 0,
                "comment": "答案触发敏感词，系统直接判0分",
                "scoring_items": [],
                "needs_review": True,
                "warning": f"触发敏感词：{hit_words}"
            }, ensure_ascii=False),
            model_used='sensitive_filter',
            confidence=1.0,
            grading_flags=json.dumps([{
                "type": "sensitive_word",
                "severity": "error",
                "desc": f"触发敏感词：{hit_words}"
            }], ensure_ascii=False),
            student_id=student_id or None
        )
        return jsonify({
            'success': True,
            'data': {
                'record_id': record_id,
                'score': 0,
                'confidence': 1.0,
                'comment': '答案触发敏感词，系统直接判0分',
                'details': {
                    'final_score': 0,
                    'comment': '答案触发敏感词，系统直接判0分',
                    'scoring_items': [],
                    'needs_review': True,
                    'warning': f'触发敏感词：{hit_words}'
                },
                'model_used': 'sensitive_filter',
                'needs_review': True,
                'warning': f'触发敏感词：{hit_words}',
                'grading_flags': [{"type": "sensitive_word", "severity": "error", "desc": f"触发敏感词：{hit_words}"}]
            }
        })

    # 使用 Qwen-Agent GradingAgent 评分
    result = await grading_engine.grade(
        question=question_text,
        answer=student_answer,
        rubric=rubric,
        max_score=max_score,
        subject=subject
    )

    # 边界检查
    result = grading_engine.boundary_check(result)

    # 记录异常到 bug_log
    if result.needs_review:
        bug_type = 'grading_failed' if result.final_score is None else 'boundary_warning'
        log_bug(
            bug_type=bug_type,
            description=result.warning or '评分异常需人工复核',
            details=json.dumps(result.dict(), ensure_ascii=False),
            question_id=question_id,
            model_used='qwen-agent'
        )

    # 证据真实性验证：检查 quoted_text 是否真实存在于原始答案中
    grading_flags = []
    if result.scoring_items:
        for item in result.scoring_items:
            quoted = item.get("quoted_text", "")
            if quoted and quoted not in student_answer:
                grading_flags.append({
                    "type": "fake_quote",
                    "severity": "warning",
                    "desc": f"评分点'{item.get('name', '')}'引用的原文不存在于学生答案中",
                    "point_name": item.get("name", "")
                })
                result.needs_review = True
                if not result.warning:
                    result.warning = ""
                result.warning += f"；评分点'{item.get('name', '')}'引用原文疑似编造"

    # 判别Agent：短答案高分检测（P2）
    if result.final_score is not None and result.final_score >= max_score * 0.8:
        stripped_answer = _re.sub(r'[\s\W]+', '', student_answer)
        if len(stripped_answer) < 10:
            grading_flags.append({
                "type": "short_answer_high_score",
                "severity": "warning",
                "desc": f"答案仅{len(stripped_answer)}个字，但得分{result.final_score}分（满分{max_score}），请人工复核"
            })
            result.needs_review = True

    # 判别Agent：全满分检测（P3 缓存幻觉）
    if result.final_score is not None and result.final_score >= max_score * 0.95:
        if result.scoring_items and len(result.scoring_items) >= 3:
            scoreable = [i for i in result.scoring_items if i.get("max_score", 0) > 0]
            if scoreable and all(
                i.get("hit") and i.get("score", 0) >= i.get("max_score", 0)
                for i in scoreable
            ):
                grading_flags.append({
                    "type": "all_perfect",
                    "severity": "info",
                    "desc": f"所有{len(scoreable)}个评分点全部满分，可能存在评分偏差，请人工复核"
                })
                result.needs_review = True
    if grading_flags:
        log_bug(
            bug_type='fake_quote',
            description='LLM 引用了不存在的原文',
            details=json.dumps(grading_flags, ensure_ascii=False),
            question_id=question_id,
            model_used='qwen-agent'
        )

    # 保存评分记录
    record_id = add_grading_record(
        question_id=question_id,
        student_answer=student_answer,
        score=result.final_score,
        details=json.dumps(result.dict(), ensure_ascii=False),
        model_used='qwen-agent',
        confidence=result.confidence,
        grading_flags=json.dumps(grading_flags, ensure_ascii=False) if grading_flags else None,
        student_id=student_id or None
    )

    # 一致性校验：同学生同题多次评分
    if student_id and question_id and result.final_score is not None:
        prev = get_previous_grade(student_id, question_id, exclude_record_id=record_id)
        if prev and prev.get('score') is not None:
            diff = abs(result.final_score - prev['score'])
            if diff > max_score * 0.2:
                flag = {
                    "type": "score_inconsistency",
                    "severity": "warning",
                    "desc": f"与上次评分({prev['score']}分)差异较大({diff:.1f}分)，可能评分不一致"
                }
                grading_flags.append(flag)
                result.needs_review = True
                # 更新记录的 grading_flags
                try:
                    from app.models.db_models import get_db_connection
                    conn = get_db_connection()
                    conn.execute(
                        'UPDATE grading_records SET grading_flags = ? WHERE id = ?',
                        (json.dumps(grading_flags, ensure_ascii=False), record_id)
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

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
            'warning': result.warning,
            'grading_flags': grading_flags
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


@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """题库总览 — 全面统计数据

    支持 ?subject=xxx 按科目过滤（科目老师只看本科目数据）
    不传 subject 则返回全部数据（管理员视图）
    """
    from app.models.db_models import get_db_connection

    subject = request.args.get('subject', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 条件子句（questions 表）
    if subject:
        q_cond = 'WHERE subject = ?'
        q_params = [subject]
    else:
        q_cond = ''
        q_params = []

    # 1. 基础统计
    cursor.execute(f'SELECT COUNT(*) FROM questions {q_cond}', q_params)
    total_questions = cursor.fetchone()[0]

    if subject:
        total_subjects = 1
    else:
        cursor.execute('SELECT COUNT(DISTINCT subject) FROM questions')
        total_subjects = cursor.fetchone()[0]

    if subject:
        cursor.execute("""
            SELECT COUNT(*) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ?
        """, [subject])
        total_gradings = cursor.fetchone()[0]

        cursor.execute("""
            SELECT AVG(gr.score) FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ? AND gr.score IS NOT NULL
        """, [subject])
    else:
        cursor.execute('SELECT COUNT(*) FROM grading_records')
        total_gradings = cursor.fetchone()[0]

        cursor.execute('SELECT AVG(score) FROM grading_records WHERE score IS NOT NULL')
    avg_score = cursor.fetchone()[0] or 0

    # 2. 各科目题目分布（管理员视图显示全部，科目老师视图不需要）
    if not subject:
        cursor.execute('SELECT subject, COUNT(*) FROM questions GROUP BY subject ORDER BY COUNT(*) DESC')
        subject_dist = [{'subject': row[0], 'count': row[1]} for row in cursor.fetchall()]
    else:
        subject_dist = []

    # 3. 评分脚本覆盖率
    if subject:
        cursor.execute("""
            SELECT COUNT(*) FROM questions
            WHERE subject = ? AND rubric_script IS NOT NULL AND rubric_script != ''
        """, [subject])
    else:
        cursor.execute("SELECT COUNT(*) FROM questions WHERE rubric_script IS NOT NULL AND rubric_script != ''")
    has_script = cursor.fetchone()[0]
    no_script = total_questions - has_script

    # 4. 测试用例覆盖
    if subject:
        cursor.execute("""
            SELECT COUNT(DISTINCT tc.question_id) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ?
        """, [subject])
        questions_with_tc = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ?
        """, [subject])
        total_test_cases = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ? AND tc.case_type = 'ai_generated'
        """, [subject])
        tc_ai = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ? AND tc.case_type = 'simulated'
        """, [subject])
        tc_simulated = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM test_cases tc
            JOIN questions q ON tc.question_id = q.id
            WHERE q.subject = ? AND tc.case_type = 'real'
        """, [subject])
        tc_real = cursor.fetchone()[0]
    else:
        cursor.execute('SELECT COUNT(DISTINCT question_id) FROM test_cases')
        questions_with_tc = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM test_cases')
        total_test_cases = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'ai_generated'")
        tc_ai = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'simulated'")
        tc_simulated = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE case_type = 'real'")
        tc_real = cursor.fetchone()[0]

    questions_without_tc = total_questions - questions_with_tc

    # 5. 质量评分分布
    quality_dist = {}
    for cond, val in [('quality_score IS NULL', 'not_evaluated'), ('quality_score < 60', 'low'), ('quality_score >= 60 AND quality_score < 80', 'medium'), ('quality_score >= 80', 'high')]:
        if subject:
            cursor.execute(f'SELECT COUNT(*) FROM questions WHERE subject = ? AND {cond}', [subject])
        else:
            cursor.execute(f'SELECT COUNT(*) FROM questions WHERE {cond}')
        quality_dist[val] = cursor.fetchone()[0]

    # 6. 最近评分趋势（最近 7 天）
    if subject:
        cursor.execute("""
            SELECT DATE(gr.graded_at) as day, COUNT(*) as cnt
            FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ? AND gr.graded_at >= DATE('now', '-7 days')
            GROUP BY DATE(gr.graded_at)
            ORDER BY day
        """, [subject])
    else:
        cursor.execute("""
            SELECT DATE(graded_at) as day, COUNT(*) as cnt
            FROM grading_records
            WHERE graded_at >= DATE('now', '-7 days')
            GROUP BY DATE(graded_at)
            ORDER BY day
        """)
    grading_trend = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

    # 7. 最近创建的题目
    cursor.execute(f'SELECT id, title, subject, created_at FROM questions {q_cond} ORDER BY created_at DESC LIMIT 5', q_params)
    recent_questions = [dict(zip(['id', 'title', 'subject', 'created_at'], row)) for row in cursor.fetchall()]

    # 8. 最近评分记录
    if subject:
        cursor.execute("""
            SELECT gr.id, gr.question_id, q.title, gr.score, gr.model_used, gr.graded_at
            FROM grading_records gr
            JOIN questions q ON gr.question_id = q.id
            WHERE q.subject = ?
            ORDER BY gr.graded_at DESC LIMIT 5
        """, [subject])
    else:
        cursor.execute("""
            SELECT gr.id, gr.question_id, q.title, gr.score, gr.model_used, gr.graded_at
            FROM grading_records gr
            LEFT JOIN questions q ON gr.question_id = q.id
            ORDER BY gr.graded_at DESC LIMIT 5
        """)
    recent_gradings = [dict(zip(['id', 'question_id', 'title', 'score', 'model_used', 'graded_at'], row)) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'subject': subject or None,
            'overview': {
                'total_questions': total_questions,
                'total_subjects': total_subjects,
                'total_gradings': total_gradings,
                'average_score': round(avg_score, 2),
            },
            'subject_dist': subject_dist,
            'rubric_coverage': {
                'has_script': has_script,
                'no_script': no_script,
            },
            'test_case_coverage': {
                'questions_with_tc': questions_with_tc,
                'questions_without_tc': questions_without_tc,
                'total_cases': total_test_cases,
                'ai_generated': tc_ai,
                'simulated': tc_simulated,
                'real': tc_real,
            },
            'quality_dist': quality_dist,
            'grading_trend': grading_trend,
            'recent_questions': recent_questions,
            'recent_gradings': recent_gradings,
        }
    })


@api_bp.route('/models/available', methods=['GET'])
def available_models():
    """获取所有可用模型列表"""
    models = model_registry.list_models()
    return jsonify({"success": True, "models": models})


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


@api_bp.route('/bugs', methods=['GET'])
def get_bugs():
    """获取 bug 日志列表"""
    import sqlite3
    import os as _os
    from config.settings import GRADING_CONFIG
    db_path = GRADING_CONFIG.get('db_path') or _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'data', 'exam_system.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    bug_type = request.args.get('bug_type', '')
    limit = int(request.args.get('limit', 100))

    if bug_type:
        cursor.execute('SELECT * FROM bug_log WHERE bug_type = ? ORDER BY created_at DESC LIMIT ?', (bug_type, limit))
    else:
        cursor.execute('SELECT * FROM bug_log ORDER BY created_at DESC LIMIT ?', (limit,))

    rows = [dict(r) for r in cursor.fetchall()]

    # 统计
    cursor.execute('SELECT bug_type, COUNT(*) as count FROM bug_log GROUP BY bug_type')
    stats = {r['bug_type']: r['count'] for r in cursor.fetchall()}

    # 按模型统计
    cursor.execute('SELECT model_used, bug_type, COUNT(*) as count FROM bug_log GROUP BY model_used, bug_type')
    by_model = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({'success': True, 'data': rows, 'stats': stats, 'by_model': by_model})


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
# 测试集管理（独立页面）
# =============================================================================

@api_bp.route('/test-cases/overview', methods=['GET'])
def test_cases_overview():
    """获取所有题目的测试用例统计概览，支持 ?subject= 筛选"""
    subject = request.args.get('subject')
    data = get_all_test_cases_overview(subject)
    return jsonify({'success': True, 'data': data})


@api_bp.route('/test-cases/all', methods=['GET'])
def test_cases_all():
    """获取所有测试用例（含题目信息），支持 ?subject= 筛选"""
    subject = request.args.get('subject')
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
    delete_test_case(test_case_id)
    return jsonify({'success': True})


@api_bp.route('/questions/<int:question_id>/generate-test-cases', methods=['POST'])
async def generate_test_cases_for_question(question_id):
    """为已有题目自动生成测试用例（支持参数化配置）"""
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404

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

    # 作答风格详细描述
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
        import re
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


# =============================================================================
# 评分脚本版本管理
# =============================================================================

@api_bp.route('/questions/<int:question_id>/script-history', methods=['GET'])
def get_question_script_history(question_id):
    """获取评分脚本版本历史"""
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    history = get_script_history(question_id)
    return jsonify({'success': True, 'data': history})


@api_bp.route('/questions/<int:question_id>/script-rollback', methods=['POST'])
def rollback_script(question_id):
    """回退到指定版本的评分脚本"""
    data = request.json
    version = data.get('version')
    if version is None:
        return jsonify({'success': False, 'error': 'version 不能为空'}), 400

    ver = get_script_version(question_id, int(version))
    if not ver:
        return jsonify({'success': False, 'error': '版本不存在'}), 404

    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404

    # update_question 内部会自动快照当前版本
    update_question(
        question_id,
        subject=q['subject'],
        title=q['title'],
        content=q['content'],
        original_text=q.get('original_text'),
        standard_answer=q.get('standard_answer'),
        rubric_rules=q.get('rubric_rules'),
        rubric_points=q.get('rubric_points'),
        rubric_script=ver['script_text'],
        rubric=q['rubric'],
        max_score=q['max_score'],
        quality_score=q.get('quality_score')
    )

    # 记录回退原因到最新版本
    history = get_script_history(question_id)
    if history:
        latest = history[0]
        from app.models.db_models import get_db_connection
        conn = get_db_connection()
        conn.execute(
            'UPDATE rubric_script_history SET note = ? WHERE id = ?',
            (f'回退到版本 {version}', latest['id'])
        )
        conn.commit()
        conn.close()

    return jsonify({'success': True, 'data': {'restored_version': int(version)}})


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
    avg_err = round(sum(errors) / len(errors), 2) if errors else None

    # 联动版本历史：更新当前脚本对应版本的验证结果
    try:
        script_text = rubric.get('rubricScript', '') or q.get('rubric_script', '')
        if script_text:
            history = get_script_history(int(question_id))
            for h in history:
                if h['script_text'] == script_text:
                    update_script_version_result(
                        int(question_id), h['version'],
                        avg_error=avg_err,
                        passed_count=passed_count,
                        total_cases=len(valid_results)
                    )
                    break
    except Exception as e:
        logger.warning(f"保存验证结果到版本历史失败: {e}")

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


# ==================== 敏感词管理 API ====================

@api_bp.route('/sensitive-words', methods=['GET'])
def list_sensitive_words():
    """获取敏感词列表"""
    subject = request.args.get('subject', '').strip() or None
    category = request.args.get('category', '').strip() or None
    severity = request.args.get('severity', '').strip() or None
    keyword = request.args.get('keyword', '').strip() or None
    words = get_sensitive_words(subject=subject, category=category,
                                keyword=keyword, severity=severity)
    return jsonify({'success': True, 'data': words})


@api_bp.route('/sensitive-words', methods=['POST'])
def create_sensitive_word():
    """添加敏感词"""
    data = request.json
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'success': False, 'message': '敏感词不能为空'}), 400
    word_id = add_sensitive_word(
        word=word,
        subject=data.get('subject', 'all'),
        category=data.get('category', 'politics'),
        severity=data.get('severity', 'high')
    )
    return jsonify({'success': True, 'data': {'id': word_id}})


@api_bp.route('/sensitive-words/<int:word_id>', methods=['PUT'])
def modify_sensitive_word(word_id):
    """更新敏感词"""
    data = request.json
    ok = update_sensitive_word(word_id, **data)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '更新失败'}), 400


@api_bp.route('/sensitive-words/<int:word_id>', methods=['DELETE'])
def remove_sensitive_word(word_id):
    """删除敏感词"""
    ok = delete_sensitive_word(word_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '删除失败'}), 404


@api_bp.route('/sensitive-words/batch', methods=['POST'])
def batch_import_sensitive_words():
    """批量导入敏感词"""
    data = request.json
    words = data.get('words', [])
    if not words:
        return jsonify({'success': False, 'message': '导入列表为空'}), 400
    # 支持纯文本格式（每行一个词）
    if isinstance(words, str):
        lines = [l.strip() for l in words.strip().split('\n') if l.strip()]
        words = [{'word': l, 'subject': data.get('subject', 'all'),
                  'category': data.get('category', 'politics'),
                  'severity': data.get('severity', 'high')} for l in lines]
    count = batch_add_sensitive_words(words)
    return jsonify({'success': True, 'data': {'imported': count}})


# ==================== 用户管理 ====================

@api_bp.route('/users', methods=['GET'])
def list_users():
    """获取用户列表"""
    users = get_users()
    return jsonify({'success': True, 'data': users})


@api_bp.route('/users', methods=['POST'])
def create_user():
    """新增用户"""
    data = request.json
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400
    if get_user(username):
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    user_id = db_add_user(
        username=username,
        display_name=data.get('display_name', ''),
        role=data.get('role', 'teacher'),
        subject=data.get('subject')
    )
    return jsonify({'success': True, 'data': {'id': user_id}})


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
def modify_user(user_id):
    """更新用户"""
    data = request.json
    ok = update_user(user_id, **data)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '更新失败'}), 400


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
def remove_user(user_id):
    """删除用户"""
    ok = delete_user(user_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '删除失败'}), 404
