"""
评分 / 历史 / 批量评分 / 统计 / 仪表盘 / 模型列表
"""
import json
import re
from flask import request, jsonify, session
from loguru import logger
from app.api_shared import (
    api_bp, grading_engine, PROVIDER_NAMES, _check_subject_access, _session_subject,
)
from app.models.db_models import (
    add_question, get_question,
    add_grading_record,
    create_batch_task, update_batch_task, get_batch_task,
    check_sensitive_words, get_previous_grade, log_bug,
    get_question_answers, get_grading_param, get_child_questions,
)
from app.models.registry import model_registry


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
            all_enabled = not enabled_models
            if available:
                for m in available:
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


@api_bp.route('/grade', methods=['POST'])
def grade_answer():
    """
    单题智能评分
    ---
    tags:
      - 评分
    summary: 对单个学生答案进行智能评分
    description: |
      使用AI模型对主观题答案进行自动评分。

      支持两种模式：
      1. 通过question_id从数据库加载题目和评分脚本
      2. 直接传入题目内容和评分标准

      评分过程包括：
      - 采分点匹配
      - 语义理解
      - 置信度评估
      - 人工复核建议
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - answer
          properties:
            question_id:
              type: integer
              description: 题目ID（可选，传了则从DB加载题目）
              example: 5
            answer:
              type: string
              description: 学生答案文本
              example: "在社会主义初级阶段，我国坚持以公有制为主体、多种所有制经济共同发展的生产资料所有制。"
            question:
              type: string
              description: 题目内容（question_id为空时必填）
              example: "简述我国社会主义初级阶段的基本经济制度。"
            max_score:
              type: number
              format: float
              description: 满分值（默认10）
              example: 8.0
            subject:
              type: string
              description: 科目（politics/chinese/english/general）
              example: "politics"
            rubric:
              type: object
              description: 自定义评分标准（可选）
            provider:
              type: string
              description: 指定模型服务商（可选）
              example: "doubao"
            model:
              type: string
              description: 指定子模型（可选）
              example: "deepseek-v3"
            student_id:
              type: string
              description: 学生ID（可选）
              example: "001"
            student_name:
              type: string
              description: 学生姓名（可选）
              example: "张三"
            exam_name:
              type: string
              description: 考试名称（可选）
              example: "期中考试"
    responses:
      200:
        description: 评分成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: object
              properties:
                record_id:
                  type: integer
                  description: 评分记录ID
                  example: 123
                score:
                  type: number
                  format: float
                  description: 评分结果
                  example: 6.0
                confidence:
                  type: number
                  format: float
                  description: 置信度（0-1）
                  example: 0.85
                comment:
                  type: string
                  description: 评语
                  example: "答案基本正确，但表述不够完整。"
                model_used:
                  type: string
                  description: 使用的模型
                  example: "qwen-agent"
                needs_review:
                  type: boolean
                  description: 是否需要人工复核
                  example: false
                warning:
                  type: string
                  description: 警告信息
                  example: null
      400:
        description: 请求参数错误
      500:
        description: 服务器内部错误
    """
    data = request.json
    question_id = data.get('question_id') or data.get('questionId')
    student_answer = data.get('answer', '')
    student_id = data.get('student_id', '')
    student_name = data.get('student_name', '')
    exam_name = data.get('exam_name', '')

    # 支持前端指定 provider 和 model（不修改全局状态，每次请求独立）
    provider = data.get('provider')
    model = data.get('model')

    # 如果传了 question_id，优先从数据库加载题目信息
    question_text = data.get('question', '')
    rubric = data.get('rubric', {})
    max_score = data.get('max_score', 10.0)
    subject = data.get('subject', 'general')
    question_answers_list = []

    # 非 question_id 模式：校验直接传的 subject
    if not question_id and not _check_subject_access(subject):
        return jsonify({'success': False, 'error': '无权评分其他科目的题目'}), 403

    if question_id:
        q = get_question(int(question_id))
        if q:
            # 科目访问控制
            if not _check_subject_access(q.get('subject', '')):
                return jsonify({'success': False, 'error': '无权评分其他科目的题目'}), 403
            question_text = q.get('content') or question_text
            max_score = q.get('max_score') or max_score
            if q.get('subject'):
                subject = q['subject']
            # 子题注入父题阅读材料
            if q.get('parent_id'):
                parent = get_question(int(q['parent_id']))
                if parent and parent.get('content'):
                    question_text = f"[Reading Material / 阅读材料]\n{parent['content']}\n\n[Question / 题目]\n{question_text}"
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
                    db_rubric = json.loads(q['rubric']) if isinstance(q['rubric'], str) else q['rubric']
                    if isinstance(db_rubric, dict):
                        for k, v in db_rubric.items():
                            if k not in rubric or not rubric[k]:
                                rubric[k] = v
                except Exception:
                    pass

            # 加载满分答案列表（三层评分用）
            question_answers_list = get_question_answers(int(question_id))
            # 英语父题：额外加载子题的采分点 JSON
            if q.get('subject') == 'english' and not q.get('parent_id'):
                children = get_child_questions(int(question_id))
                for child in children:
                    child_answers = get_question_answers(child['id'])
                    question_answers_list.extend(child_answers)

    # 读取评分策略（单题覆盖 → 全局默认）
    scoring_strategy = 'avg'
    if question_id and q and q.get('scoring_strategy'):
        scoring_strategy = q['scoring_strategy']
    else:
        scoring_strategy = get_grading_param('scoring_strategy', 'avg') or 'avg'

    # 空答案前置拦截：按科目区分判断方式，直接0分不调LLM
    from app.english_prompts import is_empty_answer_en, is_short_answer_en
    is_empty = False
    if subject == 'english':
        is_empty = is_empty_answer_en(student_answer)
    else:
        # 中文/思政/通用按字符数判断：去除空格和标点后长度 < 2
        stripped = re.sub(r'[\s\W]+', '', student_answer)
        if len(stripped) < 2:
            is_empty = True
    if is_empty:
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
            student_id=student_id or None,
            student_name=student_name or None,
            exam_name=exam_name or None
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
            student_id=student_id or None,
            student_name=student_name or None,
            exam_name=exam_name or None
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

    # 三层并行评分
    from app.three_layer_grader import three_layer_grade
    from app.qwen_engine import QwenGradingResult
    grade_result = three_layer_grade(
        grading_engine=grading_engine,
        question=question_text,
        answer=student_answer,
        rubric=rubric,
        max_score=max_score,
        subject=subject,
        question_answers=question_answers_list,
        strategy=scoring_strategy,
        provider=provider,
        model=model,
    )
    result = grade_result['llm_result']
    layer_scores = grade_result['layer_scores']
    final_score = grade_result['final_score']

    # 英语采分点精确命中时，llm_result 为 None，需要从 layer_details 构造结果
    if result is None and subject == 'english':
        sp_detail = grade_result['layer_details'].get('keyword', {})
        sp_score = layer_scores.get('keyword', 0)
        if sp_score is not None and sp_score > 0:
            # 采分点命中，构造确定性结果
            result = QwenGradingResult(
                final_score=sp_score,
                confidence=0.95,
                strategy='scoring_point_match',
                total_score=max_score,
                comment=sp_detail.get('comment', f'命中采分点，得{sp_score}分。'),
                needs_review=False,
                scoring_items=sp_detail.get('scoring_items', []),
            )

    # 如果仍然没有结果（全 miss + LLM 也失败），创建空结果
    if result is None:
        result = QwenGradingResult(
            final_score=final_score if final_score is not None else 0,
            confidence=0.3,
            strategy='fallback',
            total_score=max_score,
            comment='评分过程中出现问题，得分可能不准确。',
            needs_review=True,
            scoring_items=[],
        )

    # 用策略得分覆盖 LLM 得分
    if final_score is not None:
        result.final_score = final_score

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
        if subject == 'english':
            # 英语题按词数判断
            word_count = len(student_answer.split())
            if is_short_answer_en(student_answer):
                grading_flags.append({
                    "type": "short_answer_high_score",
                    "severity": "warning",
                    "desc": f"答案仅{word_count}个词，但得分{result.final_score}分（满分{max_score}），请人工复核"
                })
                result.needs_review = True
        else:
            stripped_answer = re.sub(r'[\s\W]+', '', student_answer)
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

    # 确定 model_used 标识
    if result.strategy == 'scoring_point_match':
        model_used_label = 'scoring_point_match'
    elif result.strategy == 'english_fallback':
        model_used_label = 'english_fallback'
    elif result.strategy == 'fallback':
        model_used_label = 'fallback'
    else:
        model_used_label = 'qwen-agent'

    # 保存评分记录
    record_id = add_grading_record(
        question_id=question_id,
        student_answer=student_answer,
        score=result.final_score,
        details=json.dumps(result.dict(), ensure_ascii=False),
        model_used=model_used_label,
        confidence=result.confidence,
        grading_flags=json.dumps(grading_flags, ensure_ascii=False) if grading_flags else None,
        student_id=student_id or None,
        student_name=student_name or None,
        exam_name=exam_name or None
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
            'model_used': model_used_label,
            'needs_review': result.needs_review,
            'warning': result.warning,
            'grading_flags': grading_flags,
            'layer_scores': layer_scores,
            'layer_details': grade_result.get('layer_details', {}),
            'scoring_strategy': scoring_strategy,
        }
    })


@api_bp.route('/history', methods=['GET'])
def list_history():
    """获取评分历史 — 非 admin 只看本科目记录"""
    from app.models.db_models import get_db_connection

    question_id = request.args.get('question_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    subject = _session_subject()  # admin 返回 None

    conn = get_db_connection()
    cursor = conn.cursor()
    if question_id:
        if subject:
            cursor.execute(
                '''SELECT gr.* FROM grading_records gr
                   JOIN questions q ON gr.question_id = q.id
                   WHERE gr.question_id = ? AND q.subject = ?
                   ORDER BY gr.graded_at DESC LIMIT ?''',
                (question_id, subject, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM grading_records WHERE question_id = ? ORDER BY graded_at DESC LIMIT ?',
                (question_id, limit)
            )
    else:
        if subject:
            cursor.execute(
                '''SELECT gr.* FROM grading_records gr
                   JOIN questions q ON gr.question_id = q.id
                   WHERE q.subject = ?
                   ORDER BY gr.graded_at DESC LIMIT ?''',
                (subject, limit)
            )
        else:
            cursor.execute('SELECT * FROM grading_records ORDER BY graded_at DESC LIMIT ?', (limit,))
    columns = [desc[0] for desc in cursor.description]
    history = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    # 转换details字符串为对象
    for h in history:
        if isinstance(h.get('details'), str):
            try:
                h['details'] = json.loads(h['details'])
            except:
                pass
    return jsonify({'success': True, 'data': history})


@api_bp.route('/batch', methods=['POST'])
def create_batch():
    """创建批量评分任务 - 使用 Qwen-Agent GradingAgent"""
    data = request.json
    task_name = data.get('task_name', '批量评分')
    answers = data.get('answers', [])

    task_id = create_batch_task(task_name, len(answers))

    # 处理批量评分 — 走三层并行评分（与单题评分一致）
    from app.three_layer_grader import three_layer_grade
    from app.qwen_engine import QwenGradingResult

    results = []
    for i, item in enumerate(answers):
        # 如果传了 question_id，从 DB 获取完整题目信息
        subj = item.get('subject', 'general')
        qid = item.get('question_id')
        rubric = item.get('rubric', {})
        question_text = item.get('question', '')
        max_score = item.get('max_score', 10.0)
        question_answers_list = []
        scoring_strategy = 'avg'

        if qid:
            q = get_question(int(qid))
            if q:
                # 科目访问控制
                if not _check_subject_access(q.get('subject', '')):
                    results.append({'question_id': qid, 'error': '无权评分其他科目的题目', 'score': None})
                    continue
                if q.get('subject'):
                    subj = q['subject']
                question_text = q.get('content') or question_text
                max_score = q.get('max_score') or max_score
                # 注入 rubric 字段
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
                if q.get('rubric'):
                    try:
                        db_rubric = json.loads(q['rubric']) if isinstance(q['rubric'], str) else q['rubric']
                        if isinstance(db_rubric, dict):
                            for k, v in db_rubric.items():
                                if k not in rubric or not rubric[k]:
                                    rubric[k] = v
                    except Exception:
                        pass
                # 加载满分答案列表
                question_answers_list = get_question_answers(int(qid))
                # 英语父题：额外加载子题的采分点
                if q.get('subject') == 'english' and not q.get('parent_id'):
                    children = get_child_questions(int(qid))
                    for child in children:
                        child_answers = get_question_answers(child['id'])
                        question_answers_list.extend(child_answers)
                # 评分策略
                if q.get('scoring_strategy'):
                    scoring_strategy = q['scoring_strategy']
                else:
                    scoring_strategy = get_grading_param('scoring_strategy', 'avg') or 'avg'

        # 三层并行评分
        grade_result = three_layer_grade(
            grading_engine=grading_engine,
            question=question_text,
            answer=item.get('answer', ''),
            rubric=rubric,
            max_score=max_score,
            subject=subj,
            question_answers=question_answers_list,
            strategy=scoring_strategy,
        )
        llm_result = grade_result.get('llm_result')
        final_score = grade_result.get('final_score')

        # 英语采分点精确命中时，llm_result 为 None
        if llm_result is None and subj == 'english':
            sp_detail = grade_result['layer_details'].get('keyword', {})
            sp_score = grade_result['layer_scores'].get('keyword', 0)
            if sp_score is not None and sp_score > 0:
                llm_result = QwenGradingResult(
                    final_score=sp_score,
                    confidence=0.95,
                    strategy='scoring_point_match',
                    total_score=max_score,
                    comment=sp_detail.get('comment', f'命中采分点，得{sp_score}分。'),
                    needs_review=False,
                    scoring_items=sp_detail.get('scoring_items', []),
                )

        if llm_result is None:
            llm_result = QwenGradingResult(
                final_score=final_score if final_score is not None else 0,
                confidence=0.3,
                strategy='fallback',
                total_score=max_score,
                comment='评分过程中出现问题，得分可能不准确。',
                needs_review=True,
                scoring_items=[],
            )

        if final_score is not None:
            llm_result.final_score = final_score

        results.append({
            'index': i,
            'score': llm_result.final_score,
            'confidence': llm_result.confidence,
            'comment': llm_result.comment
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
    """获取统计信息 — 非 admin 强制用 session.subject 过滤"""
    from app.models.db_models import get_db_connection

    subject = _session_subject()  # admin 返回 None → 全部；teacher 返回本科目
    conn = get_db_connection()
    cursor = conn.cursor()

    if subject:
        # 科目老师只看本科目
        cursor.execute('SELECT COUNT(*) FROM questions WHERE subject = ?', [subject])
        total_questions = cursor.fetchone()[0]

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
        avg_score = cursor.fetchone()[0] or 0

        subjects = {subject: total_questions}
    else:
        cursor.execute('SELECT COUNT(*) FROM questions')
        total_questions = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM grading_records')
        total_gradings = cursor.fetchone()[0]

        cursor.execute('SELECT AVG(score) FROM grading_records WHERE score IS NOT NULL')
        avg_score = cursor.fetchone()[0] or 0

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
    """题库总览 — 非 admin 强制用 session.subject 过滤"""
    from app.models.db_models import get_db_connection

    subject = _session_subject()  # admin 返回 None → 全部
    if subject is None:
        subject = request.args.get('subject', '').strip() or None  # admin 可选过滤
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
