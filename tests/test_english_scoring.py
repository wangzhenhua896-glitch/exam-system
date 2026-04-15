"""
English subject test — uses test_english.db isolated test database.

Validates:
1. English test DB data integrity (parent/child questions, scoring points, answers)
2. Scoring point JSON format compatibility with grading engine
3. english_scoring_point_match() scores correctly
4. Scoring consistency (same answer = same score every time)
"""
import json
import pytest
from app.models.db_models import get_db_connection
from app.english_grader import english_scoring_point_match


class TestEnglishDB:
    """English test DB data integrity checks"""

    def test_parent_questions_exist(self, english_db):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE parent_id IS NULL AND subject='english'")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 7, f'Expected 7 parent questions, got {count}'

    def test_child_questions_exist(self, english_db):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE parent_id IS NOT NULL AND subject='english'")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 21, f'Expected 21 child questions, got {count}'

    def test_all_have_rubric(self, english_db):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, rubric FROM questions WHERE subject='english'")
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            assert r['rubric'] and r['rubric'].strip(), f'Q{r["id"]} rubric is empty'

    def test_answers_exist(self, english_db):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM question_answers WHERE question_id IN (SELECT id FROM questions WHERE subject='english')")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 0, 'English test DB should have question answers'

    def test_scoring_point_rows_exist(self, english_db):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM question_answers WHERE scope_type='scoring_point' AND question_id IN (SELECT id FROM questions WHERE subject='english')")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 0, 'Should have scoring_point rows in question_answers'


class TestScoringPointFormat:
    """Scoring point JSON format compatibility checks"""

    def test_scoring_point_valid_json(self, english_db):
        """All scoring_point rows must be valid JSON"""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT qa.id, qa.answer_text, qa.question_id
            FROM question_answers qa
            JOIN questions q ON qa.question_id = q.id
            WHERE qa.scope_type = 'scoring_point' AND q.subject = 'english'
        """)
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            try:
                parsed = json.loads(r['answer_text'])
                assert isinstance(parsed, dict), f'Scoring point for Q{r["question_id"]} is not a dict'
            except json.JSONDecodeError:
                pytest.fail(f'Scoring point for Q{r["question_id"]} (qa_id={r["id"]}) is not valid JSON')

    def test_scoring_point_has_required_fields(self, english_db):
        """Scoring point JSON should have scoring_points array"""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT qa.answer_text, qa.question_id
            FROM question_answers qa
            JOIN questions q ON qa.question_id = q.id
            WHERE qa.scope_type = 'scoring_point' AND q.subject = 'english'
        """)
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            data = json.loads(r['answer_text'])
            assert 'scoring_points' in data, f'Q{r["question_id"]} missing scoring_points'
            assert isinstance(data['scoring_points'], list), f'Q{r["question_id"]} scoring_points is not a list'
            assert len(data['scoring_points']) > 0, f'Q{r["question_id"]} has empty scoring_points'


class TestEnglishScoring:
    """English scoring engine correctness checks"""

    def _get_scoring_data(self, english_db):
        """Get a child question with scoring_point JSON and its parent's perfect answer"""
        conn = get_db_connection()
        cur = conn.cursor()
        # Find a scoring_point row for an english child question
        cur.execute("""
            SELECT qa.id as qa_id, qa.answer_text, qa.question_id as child_id,
                   q.max_score
            FROM question_answers qa
            JOIN questions q ON qa.question_id = q.id
            WHERE qa.scope_type = 'scoring_point' AND q.subject = 'english'
            LIMIT 1
        """)
        sp_row = cur.fetchone()
        if not sp_row:
            conn.close()
            pytest.skip('No scoring_point row found')

        sp_json = json.loads(sp_row['answer_text'])
        sub_max = sp_json.get('max_score', sp_row['max_score'])
        child_id = sp_row['child_id']

        # Get parent question for perfect answer
        cur.execute("""
            SELECT parent_id FROM questions WHERE id = ?
        """, (child_id,))
        parent_row = cur.fetchone()
        if not parent_row or not parent_row['parent_id']:
            conn.close()
            pytest.skip(f'Q{child_id} has no parent')

        parent_id = parent_row['parent_id']

        # Get perfect answer from parent's question-type answer
        cur.execute("""
            SELECT answer_text FROM question_answers
            WHERE question_id = ? AND scope_type = 'question'
            ORDER BY score_ratio DESC LIMIT 1
        """, (parent_id,))
        ans = cur.fetchone()
        conn.close()

        if not ans:
            pytest.skip(f'Parent Q{parent_id} has no perfect answer')

        return {
            'child_id': child_id,
            'parent_id': parent_id,
            'max_score': sub_max,
            'scoring_points': sp_json,
            'perfect_answer': ans['answer_text'],
        }

    def test_perfect_answer_scores_full(self, english_db):
        """Perfect answer should score full marks"""
        data = self._get_scoring_data(english_db)
        score, details = english_scoring_point_match(
            data['perfect_answer'],
            data['scoring_points'],
            data['max_score']
        )
        assert score == data['max_score'], (
            f'Perfect answer scored {score}/{data["max_score"]}. '
            f'Details: {json.dumps(details, ensure_ascii=False)[:200]}'
        )

    def test_empty_answer_scores_zero(self, english_db):
        """Empty answer should score 0"""
        data = self._get_scoring_data(english_db)
        score, details = english_scoring_point_match(
            '',
            data['scoring_points'],
            data['max_score']
        )
        assert score == 0, f'Empty answer should score 0, got {score}'

    def test_scoring_consistency(self, english_db):
        """Same answer scored multiple times must give same result"""
        data = self._get_scoring_data(english_db)
        scores = []
        for _ in range(3):
            score, _ = english_scoring_point_match(
                data['perfect_answer'],
                data['scoring_points'],
                data['max_score']
            )
            scores.append(score)
        assert len(set(scores)) == 1, f'Inconsistent scores: {scores}'

    def test_partial_answer_scores_between(self, english_db):
        """Partial answer should score between 0 and max"""
        data = self._get_scoring_data(english_db)
        # Use first 20 chars of perfect answer as partial
        partial = data['perfect_answer'][:20]
        if not partial.strip():
            pytest.skip('Perfect answer starts with whitespace')
        score, _ = english_scoring_point_match(
            partial,
            data['scoring_points'],
            data['max_score']
        )
        assert 0 <= score <= data['max_score'], f'Partial score {score} out of range [0, {data["max_score"]}]'
