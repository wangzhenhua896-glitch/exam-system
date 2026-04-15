"""
评分脚本生成 / 自查 / 验证 / 版本管理 / Bug 日志
"""
import json
import re
from flask import request, jsonify, session
from loguru import logger
from app.api_shared import (
    api_bp, grading_engine, _check_subject_access, _session_subject,
    RUBRIC_SCRIPT_SYSTEM_PROMPT,
)
from app.models.db_models import (
    get_question, update_question,
    get_test_cases, update_test_case_result,
    save_script_version, get_script_history, get_script_version,
    get_script_history as _get_script_history,
    update_script_version_result,
    log_bug,
)
from app.english_prompts import (
    RUBRIC_SCRIPT_SYSTEM_PROMPT_EN,
    SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN,
    make_rubric_points_prompt_en,
    make_rubric_script_prompt_en,
    make_self_check_prompt_en,
)


@api_bp.route('/generate-rubric-points', methods=['POST'])
def generate_rubric_points():
    """AI 从标准答案中提取分数分布（得分要点）"""
    data = request.json
    content = data.get('content', '').strip()
    score = data.get('score', 10)
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_rules = data.get('rubricRules', '').strip()
    subject = data.get('subject', 'general')
    # 非 admin 强制用 session.subject
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj

    if not content:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空'}), 400

    if subject == 'english':
        user_prompt = make_rubric_points_prompt_en(content, score, standard_answer, rubric_rules)
        system_msg = "You are an assessment expert skilled at extracting structured scoring points from standard answers."
    else:
        user_prompt = f"""请根据以下题目、标准答案和评分规则，提取得分要点，生成分数分布：

【题目】
{content}

【满分】
{score} 分

【标准答案】
{standard_answer}"""

        if rubric_rules:
            user_prompt += f"\n\n【评分规则】\n{rubric_rules}"

        user_prompt += """
要求：
1. 将标准答案拆分为若干得分要点
2. 每个要点一行，格式：要点描述 (X分)
3. 所有要点分值之和 = 满分
4. 参考评分规则中的分值分配和扣分要求
5. 使用确定性语言，不含模糊表述
6. 直接输出得分要点，每行一个，不要加编号或其他内容"""
        system_msg = "你是一个命题专家，擅长从标准答案中提取结构化得分要点。"

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        points = response.choices[0].message.content.strip()
        if not points or len(points) < 10:
            return jsonify({'success': False, 'error': 'AI 生成的内容过短，请重试'}), 500
        return jsonify({'success': True, 'data': {'rubricPoints': points}})
    except Exception as e:
        logger.error(f"生成分数分布失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    subject = data.get('subject', 'general')
    # 非 admin 强制用 session.subject
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj

    if not content:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空，请先填写标准答案'}), 400

    # 构建用户提示词（按科目区分中英文）
    if subject == 'english':
        system_prompt = RUBRIC_SCRIPT_SYSTEM_PROMPT_EN
        user_prompt = make_rubric_script_prompt_en(content, score, standard_answer, rubric_rules, rubric_points, ai_rubric)
    else:
        system_prompt = RUBRIC_SCRIPT_SYSTEM_PROMPT
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
4. 每个得分点必须包含【必含关键词】（至少2个）和【等价表述】（至少5个，覆盖同义词/口语化/上下位/部分匹配等多个维度）
5. 指定 JSON 输出格式：{"scoring_items": [{"name": "要点1：XXX", "score": X, "max_score": X, "hit": true/false, "reason": "...", "quoted_text": "..."}], "评语": "..."}，总分由系统自动累加
6. 直接输出评分脚本内容，不要加任何解释"""

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": system_prompt},
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


@api_bp.route('/self-check-rubric', methods=['POST'])
def self_check_rubric():
    """评分约定自查：让 AI 检查现有评分脚本并给出问题和完善建议"""
    data = request.json
    content = data.get('content', '').strip()
    score = data.get('score', 10)
    standard_answer = data.get('standardAnswer', '').strip()
    rubric_script = data.get('rubricScript', '').strip()
    subject = data.get('subject', 'general')
    # 非 admin 强制用 session.subject
    session_subj = _session_subject()
    if session_subj:
        subject = session_subj

    if not content:
        return jsonify({'success': False, 'error': '题目内容不能为空'}), 400
    if not standard_answer:
        return jsonify({'success': False, 'error': '标准答案不能为空'}), 400
    if not rubric_script:
        return jsonify({'success': False, 'error': '评分约定内容不能为空'}), 400

    if subject == 'english':
        system_prompt = SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN
        user_prompt = make_self_check_prompt_en(content, score, standard_answer, rubric_script)
    else:
        system_prompt = """你是一位资深教育测评专家，专门负责审查评分脚本的质量。

你的任务：仔细审查提供的评分脚本，找出所有问题，并给出完善后的版本。

审查要点：
1. **自包含性**：评分脚本是否包含了所有必要的评分信息？阅卷模型只看到脚本和答案，没有题目原文。
2. **确定性语言**：是否还存在"酌情给分"、"视情况"、"适当给分"、"根据质量"等模糊表述？
3. **分值明确**：每个得分点是否有明确的分值（不能有范围值如"1-2分"）？
4. **关键词完整性**：关键词列表是否覆盖了标准答案中的核心概念？是否有遗漏的重要等价表述？
5. **反作弊规则**：是否包含复制题干、空白作答、答非所问等判0分条件？
6. **输出格式**：是否指定了清晰的 JSON 输出格式？
7. **逻辑矛盾**：各评分规则之间是否存在矛盾或冲突？
8. **边界情况**：是否考虑了部分作答、口语化表达、字数很少等边界情况？

请严格按以下 JSON 格式输出（不要输出其他内容）：
```json
{
  "issues": [
    {
      "category": "问题分类",
      "description": "具体问题描述",
      "location": "问题所在位置（如第X行/第X段）"
    }
  ],
  "issue_count": 问题总数,
  "improved_script": "完善后的评分脚本全文（如果没有问题则返回原文）"
}
```"""

        user_prompt = f"""【题目内容】
{content}

【满分】
{score} 分

【标准答案】
{standard_answer}

【待审查的评分约定】
{rubric_script}

请仔细审查以上评分约定，找出所有问题，并给出完善后的版本。"""

    try:
        response = grading_engine.client.chat.completions.create(
            model=grading_engine.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content.strip()

        # 提取 JSON
        result = None
        # 尝试直接解析
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # 从 ```json ... ``` 中提取
            m = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            if result is None:
                # 尝试找 { ... } 块
                m = re.search(r'\{[\s\S]*\}', raw)
                if m:
                    try:
                        result = json.loads(m.group(0))
                    except json.JSONDecodeError:
                        pass

        if result is None:
            return jsonify({'success': False, 'error': 'AI 返回结果解析失败，请重试'}), 500

        issues = result.get('issues', [])
        issue_count = result.get('issue_count', len(issues))
        improved_script = result.get('improved_script', rubric_script)

        logger.info(f"约定自查完成，发现问题 {issue_count} 个")
        return jsonify({
            'success': True,
            'data': {
                'issues': issues,
                'issue_count': issue_count,
                'improved_script': improved_script
            }
        })
    except Exception as e:
        logger.error(f"约定自查失败：{e}")
        return jsonify({'success': False, 'error': f'自查失败：{str(e)}'}), 500


@api_bp.route('/bugs', methods=['GET'])
def get_bugs():
    """获取 bug 日志列表"""
    from app.models.db_models import get_db_connection
    conn = get_db_connection()
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


@api_bp.route('/questions/<int:question_id>/script-history', methods=['GET'])
def get_question_script_history(question_id):
    """获取评分脚本版本历史"""
    q = get_question(question_id)
    if not q:
        return jsonify({'success': False, 'error': '题目不存在'}), 404
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权访问其他科目的版本历史'}), 403
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
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权修改其他科目的评分脚本'}), 403

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


@api_bp.route('/verify-rubric', methods=['POST'])
def verify_rubric():
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
    # 科目访问控制
    if not _check_subject_access(q.get('subject', '')):
        return jsonify({'success': False, 'error': '无权验证其他科目的题目'}), 403

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
    subject = q.get('subject', 'general')

    # 逐个评分
    results = []
    for tc in cases:
        try:
            result = grading_engine.grade(
                question=question_text,
                answer=tc['answer_text'],
                rubric=rubric,
                max_score=max_score,
                subject=subject
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
