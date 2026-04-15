"""
批量评分
路由：/batch (POST), /batch/<id> (GET)
"""
import json
from flask import request, jsonify
from app.api_shared import (
    api_bp, grading_engine, _check_subject_access,
)
from app.models.db_models import (
    get_question,
    create_batch_task, update_batch_task, get_batch_task,
    get_question_answers, get_grading_param, get_child_questions,
)


@api_bp.route('/batch', methods=['POST'])
def create_batch():
    """创建批量评分任务 — 走三层并行评分"""
    data = request.json
    task_name = data.get('task_name', '批量评分')
    answers = data.get('answers', [])

    task_id = create_batch_task(task_name, len(answers))

    from app.three_layer_grader import three_layer_grade
    from app.qwen_engine import QwenGradingResult

    results = []
    for i, item in enumerate(answers):
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
                if not _check_subject_access(q.get('subject', '')):
                    results.append({'question_id': qid, 'error': '无权评分其他科目的题目', 'score': None})
                    continue
                if q.get('subject'):
                    subj = q['subject']
                question_text = q.get('content') or question_text
                max_score = q.get('max_score') or max_score
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
                question_answers_list = get_question_answers(int(qid))
                if q.get('subject') == 'english' and not q.get('parent_id'):
                    children = get_child_questions(int(qid))
                    for child in children:
                        child_answers = get_question_answers(child['id'])
                        question_answers_list.extend(child_answers)
                if q.get('scoring_strategy'):
                    scoring_strategy = q['scoring_strategy']
                else:
                    scoring_strategy = get_grading_param('scoring_strategy', 'avg') or 'avg'

        grade_result = three_layer_grade(
            grading_engine=grading_engine, question=question_text,
            answer=item.get('answer', ''), rubric=rubric, max_score=max_score,
            subject=subj, question_answers=question_answers_list, strategy=scoring_strategy,
        )
        llm_result = grade_result.get('llm_result')
        final_score = grade_result.get('final_score')

        if llm_result is None and subj == 'english':
            sp_detail = grade_result['layer_details'].get('keyword', {})
            sp_score = grade_result['layer_scores'].get('keyword', 0)
            if sp_score is not None and sp_score > 0:
                llm_result = QwenGradingResult(
                    final_score=sp_score, confidence=0.95, strategy='scoring_point_match',
                    total_score=max_score, comment=sp_detail.get('comment', f'命中采分点，得{sp_score}分。'),
                    needs_review=False, scoring_items=sp_detail.get('scoring_items', []),
                )

        if llm_result is None:
            llm_result = QwenGradingResult(
                final_score=final_score if final_score is not None else 0,
                confidence=0.3, strategy='fallback', total_score=max_score,
                comment='评分过程中出现问题，得分可能不准确。',
                needs_review=True, scoring_items=[],
            )

        if final_score is not None:
            llm_result.final_score = final_score

        results.append({'index': i, 'score': llm_result.final_score, 'confidence': llm_result.confidence, 'comment': llm_result.comment})
        update_batch_task(task_id, i + 1, json.dumps(results, ensure_ascii=False), 'running')

    update_batch_task(task_id, len(answers), json.dumps(results, ensure_ascii=False), 'completed')

    return jsonify({'success': True, 'data': {'task_id': task_id, 'results': results}})


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
        except Exception:
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
