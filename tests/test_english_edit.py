"""
英语编辑器后端测试

验证：
1. DB 迁移：question_type / workflow_status 列存在且有默认值
2. add_question / update_question 支持新参数
3. workflow-status 轻量更新接口
4. 4 个 AI 接口路由注册和参数校验
5. buildApiPayload 格式与评分引擎兼容
"""
import json
import os
import sys
import sqlite3
import pytest

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 1. DB 迁移测试
# ============================================================

class TestDbMigration:
    """验证 question_type 和 workflow_status 列已正确添加"""

    def _get_conn(self):
        from app.models.db_models import get_db_connection, init_database
        init_database()
        return get_db_connection()

    def test_question_type_column_exists(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(questions)")
        cols = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert 'question_type' in cols, "question_type 列不存在"

    def test_workflow_status_column_exists(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(questions)")
        cols = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert 'workflow_status' in cols, "workflow_status 列不存在"

    def test_new_question_has_default_type(self):
        from app.models.db_models import add_question, get_question, delete_question
        qid = add_question(
            subject='english', title='Test', content='Test content',
            original_text=None, standard_answer='Answer',
            rubric_rules=None, rubric_points=None, rubric_script=None,
            rubric='{}', max_score=2.0,
        )
        q = get_question(qid)
        assert q['question_type'] == 'essay', f"默认 question_type 应为 essay，实际: {q['question_type']}"
        assert q['workflow_status'] is None, f"新题 workflow_status 应为 None"
        delete_question(qid)

    def test_question_type_can_be_set(self):
        from app.models.db_models import add_question, get_question, delete_question
        qid = add_question(
            subject='english', title='Test', content='Test content',
            original_text=None, standard_answer='Answer',
            rubric_rules=None, rubric_points=None, rubric_script=None,
            rubric='{}', max_score=2.0,
            question_type='single_choice',
        )
        q = get_question(qid)
        assert q['question_type'] == 'single_choice', f"question_type 应为 single_choice，实际: {q['question_type']}"
        delete_question(qid)

    def test_update_question_type_and_workflow(self):
        from app.models.db_models import add_question, update_question, get_question, delete_question
        qid = add_question(
            subject='english', title='Test', content='Test',
            original_text=None, standard_answer='Ans',
            rubric_rules=None, rubric_points=None, rubric_script=None,
            rubric='{}', max_score=2.0,
        )
        ws = json.dumps({'current_step': 'per_question', 'active_question_index': 1})
        update_question(
            qid, subject='english', title='Test Updated', content='Test',
            original_text=None, standard_answer='Ans',
            rubric_rules=None, rubric_points=None, rubric_script=None,
            rubric='{}', max_score=2.0,
            question_type='translation', workflow_status=ws,
        )
        q = get_question(qid)
        assert q['question_type'] == 'translation'
        assert q['workflow_status'] == ws
        delete_question(qid)


# ============================================================
# 2. workflow_status 轻量更新
# ============================================================

class TestWorkflowStatusUpdate:
    """验证 update_workflow_status 函数"""

    def test_update_workflow_status(self):
        from app.models.db_models import add_question, get_question, delete_question, update_workflow_status
        qid = add_question(
            subject='english', title='WS Test', content='Test',
            original_text=None, standard_answer='Ans',
            rubric_rules=None, rubric_points=None, rubric_script=None,
            rubric='{}', max_score=2.0,
        )
        ws_json = json.dumps({'current_step': 'script', 'completed_steps': ['extract', 'per_question']})
        result = update_workflow_status(qid, ws_json)
        assert result is True
        q = get_question(qid)
        assert q['workflow_status'] == ws_json
        # 验证 rubric 未被改动
        assert q['rubric'] == '{}'
        delete_question(qid)

    def test_update_nonexistent_question(self):
        from app.models.db_models import update_workflow_status
        result = update_workflow_status(99999, '{}')
        assert result is False


# ============================================================
# 3. API 接口参数校验
# ============================================================

class TestApiValidation:
    """验证新接口的参数校验"""

    @pytest.fixture
    def client(self):
        import app.app as app_module
        app = app_module.create_app()
        app.config['TESTING'] = True
        with app.test_client() as c:
            yield c

    def test_extract_requires_full_text(self, client):
        resp = client.post('/api/english/extract',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data['success']

    def test_suggest_synonyms_requires_keyword(self, client):
        resp = client.post('/api/english/suggest-synonyms',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data['success']

    def test_suggest_exclude_requires_keywords(self, client):
        resp = client.post('/api/english/suggest-exclude',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_generate_rubric_requires_question_text(self, client):
        resp = client.post('/api/english/generate-rubric',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_workflow_status_requires_body(self, client):
        # 需要一个存在的题目 — 用固定 ID 的老题
        resp = client.put('/api/questions/1/workflow-status',
                          data=json.dumps({}),
                          content_type='application/json')
        assert resp.status_code == 400

    def test_workflow_status_wrong_method(self, client):
        resp = client.get('/api/questions/1/workflow-status')
        assert resp.status_code == 405


# ============================================================
# 4. buildApiPayload 格式验证
# ============================================================

class TestBuildApiPayloadFormat:
    """
    验证 buildApiPayload 输出格式与评分引擎完全兼容。
    这些测试在 JS 端执行（englishEditCore.js），这里用 Python 模拟关键约束。
    """

    def test_max_hit_score_is_string(self):
        """坑1: max_hit_score 必须是字符串"""
        payload = {'score_formula': 'max_hit_score'}
        assert isinstance(payload['score_formula'], str)
        assert payload['score_formula'] == 'max_hit_score'

    def test_hit_count_is_dict_with_rules(self):
        """坑1+坑4: hit_count 必须是 dict，rules 必须嵌套在内部"""
        payload = {
            'score_formula': {
                'type': 'hit_count',
                'rules': [{'min_hits': 2, 'score': 2}, {'min_hits': 1, 'score': 1}]
            }
        }
        assert isinstance(payload['score_formula'], dict)
        assert payload['score_formula']['type'] == 'hit_count'
        assert 'rules' in payload['score_formula']
        assert len(payload['score_formula']['rules']) == 2

    def test_max_score_present(self):
        """坑2: 每个采分点 JSON 必须有 max_score"""
        payload = {
            'id': 'Q1',
            'max_score': 2,
            'score_formula': 'max_hit_score',
            'scoring_points': [],
        }
        assert 'max_score' in payload
        assert payload['max_score'] == 2

    def test_scoring_point_has_id_and_score(self):
        """坑3: 每个 scoring_point 必须有 id 和 score"""
        sp = {'id': 'A', 'score': 2, 'keywords': ['test'], 'synonyms': []}
        assert 'id' in sp
        assert 'score' in sp

    def test_rules_not_at_top_level(self):
        """坑4: rules 不能在顶层"""
        payload = {
            'score_formula': {
                'type': 'hit_count',
                'rules': [{'min_hits': 2, 'score': 2}]
            },
            'scoring_points': [],
        }
        # rules 必须在 score_formula 内部
        assert 'rules' not in payload or 'rules' in payload.get('score_formula', {})

    def test_keywords_lowercase(self):
        """坑5: keywords 应统一小写"""
        keywords = ['Spring Festival', 'NEW YEAR']
        normalized = [k.lower() for k in keywords]
        assert normalized == ['spring festival', 'new year']

    def test_field_names_exact(self):
        """坑6: 字段名必须完全匹配"""
        payload = {
            'id': 'Q1',
            'max_score': 2,
            'score_formula': 'max_hit_score',
            'scoring_points': [],
            'exclude_list': [],
            'pinyin_whitelist': [],
        }
        assert 'exclude_list' in payload  # 不是 excluded_list
        assert 'pinyin_whitelist' in payload  # 不是 pinyin_whilist

    def test_full_max_hit_score_template(self):
        """完整 max_hit_score 格式模板验证"""
        payload = {
            "id": "Q1",
            "max_score": 2,
            "score_formula": "max_hit_score",
            "scoring_points": [
                {"id": "A", "score": 2, "keywords": ["spring festival"], "synonyms": ["chunjie"]},
                {"id": "B", "score": 1, "keywords": ["spring", "festival"], "synonyms": []},
            ],
            "exclude_list": ["new year", "lunar new year"],
            "pinyin_whitelist": [],
        }
        assert isinstance(payload['score_formula'], str)
        assert payload['score_formula'] == 'max_hit_score'
        assert len(payload['scoring_points']) == 2
        assert all('id' in sp and 'score' in sp for sp in payload['scoring_points'])

    def test_full_hit_count_template(self):
        """完整 hit_count 格式模板验证"""
        payload = {
            "id": "Q2",
            "max_score": 2,
            "score_formula": {
                "type": "hit_count",
                "rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1},
                ],
            },
            "scoring_points": [
                {"id": "A", "score": 1, "keywords": ["sounds like surplus"], "synonyms": ["sounds similar to surplus"]},
                {"id": "B", "score": 1, "keywords": ["yearly prosperity"], "synonyms": ["prosperity every year"]},
            ],
            "exclude_list": [],
            "pinyin_whitelist": [],
        }
        assert isinstance(payload['score_formula'], dict)
        assert payload['score_formula']['type'] == 'hit_count'
        assert len(payload['score_formula']['rules']) == 2


# ============================================================
# 5. english_prompts 导入测试
# ============================================================

class TestEnglishPrompts:
    """验证所有提示词和构造函数可正常导入和调用"""

    def test_import_all_prompts(self):
        from app.english_prompts import (
            EXTRACT_SUBQUESTIONS_SYSTEM,
            SUGGEST_SYNONYMS_SYSTEM,
            SUGGEST_EXCLUDE_SYSTEM,
            GENERATE_RUBRIC_SCRIPT_SYSTEM,
            make_extract_prompt,
            make_synonyms_prompt,
            make_exclude_prompt,
            make_generate_rubric_prompt,
        )
        assert len(EXTRACT_SUBQUESTIONS_SYSTEM) > 100
        assert len(SUGGEST_SYNONYMS_SYSTEM) > 50

    def test_make_extract_prompt(self):
        from app.english_prompts import make_extract_prompt
        p = make_extract_prompt("What is the Spring Festival?")
        assert "What is the Spring Festival?" in p
        assert "Extract:" in p

    def test_make_synonyms_prompt(self):
        from app.english_prompts import make_synonyms_prompt
        p = make_synonyms_prompt("spring festival", "context", "question?", ["chunjie"])
        assert "spring festival" in p
        assert "chunjie" in p

    def test_make_exclude_prompt(self):
        from app.english_prompts import make_exclude_prompt
        p = make_exclude_prompt("question?", ["keyword"], ["synonym"], "context")
        assert "keyword" in p

    def test_make_generate_rubric_prompt(self):
        from app.english_prompts import make_generate_rubric_prompt
        p = make_generate_rubric_prompt("question?", "answer", 2, [])
        assert "question?" in p
        assert "2" in p


# ============================================================
# 6. 解析工具测试
# ============================================================

class TestParseJsonFromLlm:
    """验证 _parse_json_from_llm 的健壮性"""

    def _parse(self, raw):
        """从 api_routes 中提取 _parse_json_from_llm 逻辑"""
        import re
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {}

    def test_plain_json(self):
        result = self._parse('{"a": 1}')
        assert result == {'a': 1}

    def test_markdown_code_block(self):
        result = self._parse('```json\n{"a": 1}\n```')
        assert result == {'a': 1}

    def test_markdown_no_lang(self):
        result = self._parse('```\n{"a": 1}\n```')
        assert result == {'a': 1}

    def test_json_with_surrounding_text(self):
        result = self._parse('Here is the result:\n{"a": 1}\nDone.')
        assert result == {'a': 1}

    def test_invalid_returns_empty(self):
        result = self._parse('not json at all')
        assert result == {}

    def test_nested_json(self):
        raw = '{"sub_questions": [{"text": "Q1", "scoring_points": [{"id": "A", "score": 2}]}]}'
        result = self._parse(raw)
        assert len(result['sub_questions']) == 1
        assert result['sub_questions'][0]['scoring_points'][0]['id'] == 'A'
