"""
英语科目 Prompt 模块

从 api_routes.py 迁出的所有英语相关 prompt 常量、构造函数、工具函数。
"""
import json

# ============================================================
# 系统提示词常量
# ============================================================

RUBRIC_SCRIPT_SYSTEM_PROMPT_EN = """You are an expert educational assessment specialist. Your task is to convert scoring criteria into a structured, unambiguous grading script.

The grading script will be saved and used as the SOLE basis for automated grading. During grading, the model will only see this script and the student's answer — no other context.

Requirements:
1. **Self-contained**: Anyone/model with the script can grade accurately without extra context
2. **Cross-model consistent**: Different LLMs with the same script + answer should give the same score
3. **Robust**: Handle all answer types (complete, partial, colloquial, brief, off-topic, blank)

## Script Structure (in order)

- [Question Information]: Full restatement of the question and max score
- [Key Answer Points]: Core points from the standard answer, each with:
  - Core meaning (what the point is about)
  - Keywords and equivalent expressions (how students might phrase it)
- [Item-by-Item Scoring Rules]: For each scoring point:
  - **Full credit condition**: What earns full marks, with specific check steps
  - **Partial credit condition**: What earns partial marks, how much, with examples
  - **No credit condition**: What earns zero
  - **Common confusions**: What looks right but shouldn't score
  - Each point must list [Required Keywords] and [Equivalent Expressions]
- [Answer Type Classification]: Pre-define scoring for common patterns (complete, partial, blank, colloquial, off-topic)
- [Deduction Rules]: Explicit deduction conditions; write "No additional deductions" if none
- [Total Score Calculation]: Total = sum of items - deductions, range [0, max_score]
- [Output Format]: Force JSON output format

## Language Rules
- **NEVER use**: "as appropriate", "depending on", "based on quality", "generally", "usually", "adequately"
- **ALWAYS use**: "If... then score X", "As long as... score X", "If not mentioned... score 0"
- Each scoring point must have explicit numeric values, no ranges
- Partial credit must specify exact values

## Consistency
- Use keyword match + semantic match dual judgment
- List [Required Keywords] for fast check (at least 2 per point, prioritize domain-specific terms)
- List [Equivalent Expressions] for semantic match (at least 5 per point, covering:
  - Synonyms (e.g., "analyze" → "examine", "evaluate")
  - Paraphrases (e.g., "improve efficiency" → "make things work better")
  - Partial matches (e.g., "economic growth" → "growth" alone counts)
  - Related concepts (e.g., "supply and demand" → "market forces"))
- Clearly state "must satisfy ALL" vs "satisfy ANY ONE"
- Keyword match takes priority over semantic match

## Output Format
- Output structured text, not code/functions
- Output the grading script directly, no explanations"""


QUALITY_EVALUATION_SYSTEM_PROMPT_EN = """You are an expert educational assessment quality reviewer. Your task is to identify potential quality issues before a question is saved, preventing wasted grading effort.

Your task: Based on the provided question information, evaluate the quality from 4 dimensions and output a structured report.

## Evaluation Dimensions

### I. Question Itself (4 checks)
1. **Ambiguous wording**: The question is vague — students don't know what to answer.
2. **Multiple interpretations**: The question can be understood in different ways.
3. **Missing constraints**: Too broad a scope; the standard answer can't cover all correct responses.
4. **Mismatch with standard answer**: The question asks one thing but the answer addresses another.

### II. Standard Answer (4 checks)
5. **Incomplete**: Missing key content required by the question.
6. **Factually incorrect**: Contains wrong or outdated information.
7. **Vague points**: Uses vague language like "etc." or "related points" without elaboration.
8. **Inconsistent with scoring points**: Answer lists N points but scoring criteria only cover some.

### III. Scoring Rules (4 checks)
9. **Unreasonable score allocation**: Points don't sum to max score, or heavily skewed.
10. **Overly broad criteria**: e.g. "full marks if correct" without specific conditions.
11. **Missing partial credit rules**: All-or-nothing scoring with no partial credit defined.
12. **Missing keywords**: No judgment keywords provided for scoring points.

### IV. Overall (2 checks)
13. **Difficulty-score mismatch**: Very easy question with high score, or vice versa.
14. **Unclear question type**: Can't tell if it's short answer, essay, definition, etc.

## Scoring
- Base score: 100
- Each error: -15 points
- Each warning: -8 points
- Each info: -3 points
- overall_score = max(0, 100 - total deductions)

## Verdict Rules
- overall_score >= 80 and no errors → verdict = "pass"
- Any error or overall_score < 60 → verdict = "fail"
- Otherwise → verdict = "warning"

## Output Format
Strictly output this JSON, no other content:
{"overall_score": integer, "verdict": "pass"/"warning"/"fail", "issues": [{"category": "Question/Answer/Scoring/Overall", "severity": "info/warning/error", "description": "specific issue"}], "suggestions": ["suggestion 1", "suggestion 2"]}

## Important
- If quality is good, issues can be empty array, overall_score 95-100
- Only report issues that actually affect grading accuracy
- Be specific in descriptions, not generic"""


SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN = """You are an expert educational assessment specialist responsible for reviewing grading scripts.

Your task: Carefully review the provided grading script, identify all issues, and provide an improved version.

Review checklist:
1. **Self-contained**: Does the script contain all necessary grading info? The grader only sees the script and the answer, not the original question.
2. **Deterministic language**: Any vague phrasing like "as appropriate", "depending on", "based on quality"?
3. **Explicit scores**: Each scoring point has a definite value (no ranges like "1-2 points")?
4. **Keyword completeness**: Do keyword lists cover core concepts from the standard answer? Missing equivalent expressions?
5. **Anti-cheat rules**: Does it include copy-the-question, blank answer, off-topic as 0-score conditions?
6. **Output format**: Is there a clear JSON output format specified?
7. **Logical conflicts**: Any contradictions between scoring rules?
8. **Edge cases**: Does it handle partial answers, colloquial expressions, very short answers?

Output strictly this JSON format (no other content):
```json
{
  "issues": [
    {
      "category": "issue category",
      "description": "specific issue description",
      "location": "where in the script (e.g. Section X / Paragraph Y)"
    }
  ],
  "issue_count": total_issues,
  "improved_script": "improved grading script text (return original if no issues)"
}
```"""


AUTO_GEN_QUESTION_SYSTEM_EN = """You are an expert English exam question writer.

Requirements:
1. Questions must be short-answer or essay type (no multiple choice, fill-in-blank, or true/false)
2. Questions should match secondary/vocational school student level
3. Each question must have a definitive standard answer (no open-ended discussion)
4. Scoring points must be clear and quantifiable

Output format (strict JSON):
{
    "title": "Brief question title (under 15 words)",
    "content": "Full question text",
    "max_score": score (integer),
    "difficulty": "easy/medium/hard",
    "knowledge": "Knowledge points tested",
    "content_type": "Short Answer",
    "standard_answer": "Complete standard answer with all scoring points",
    "rubric_rules": "Overall scoring rules",
    "rubric_points": "One point per line, format: Point description (X points)"
}

Note:
- Sum of rubric_points scores must equal max_score
- Standard answer must be complete and accurate
- Output JSON only, no explanations"""


AUTO_GEN_TESTCASE_SYSTEM_EN = """You are an experienced English teacher familiar with various student response patterns.

Your task: Based on the question and standard answer, generate multiple simulated student responses covering different score levels.

Output format (strict JSON array):
[
    {
        "description": "Brief description",
        "case_type": "ai_generated",
        "answer_text": "Simulated student response",
        "expected_score": expected score
    }
]

Note: expected_score must be a specific number. Scores should form a gradient. Output JSON only."""


# ============================================================
# 风格指南字典
# ============================================================

STYLE_GUIDE_EN = {
    'formal': 'Standard academic English, clear logic, all key points covered, like a top student response',
    'colloquial': 'Informal/casual English, incomplete sentences, grammatical errors, but core meaning is there',
    'incomplete': 'Partially correct but missing key points, resulting in partial score loss',
    'off-topic': 'Did not understand the question, irrelevant content, completely off-topic',
    'verbatim copy': 'Copied the question or standard answer verbatim (for testing anti-cheat rules)',
    'blank': "Blank, only wrote \"I don't know\", or completely irrelevant content",
}


# ============================================================
# User Prompt 构造函数
# ============================================================

def make_rubric_points_prompt_en(content: str, score: int, standard_answer: str, rubric_rules: str = '') -> str:
    """generate_rubric_points 端点的英语 user_prompt"""
    prompt = f"""Extract scoring points from the following question and standard answer:

[Question]
{content}

[Max Score]
{score} points

[Standard Answer]
{standard_answer}"""

    if rubric_rules:
        prompt += f"\n\n[Scoring Rules]\n{rubric_rules}"

    prompt += """
Requirements:
1. Break the standard answer into individual scoring points
2. One point per line, format: Point description (X points)
3. Sum of all points = max score
4. Use deterministic language, no ambiguity
5. Output scoring points directly, one per line, no numbering"""
    return prompt


def make_rubric_script_prompt_en(
    content: str,
    score: int,
    standard_answer: str,
    rubric_rules: str = '',
    rubric_points: str = '',
    ai_rubric: str = '',
) -> str:
    """generate_rubric_script 端点的英语 user_prompt"""
    prompt = f"""Please generate a structured grading script based on the following:

[Question]
{content}

[Max Score]
{score} points

[Standard Answer]
{standard_answer}"""

    if rubric_rules:
        prompt += f"\n\n[Scoring Rules]\n{rubric_rules}"
    if rubric_points:
        prompt += f"\n\n[Score Distribution / Key Points]\n{rubric_points}"
    if ai_rubric:
        prompt += f"\n\n[Grading Instructions / Notes]\n{ai_rubric}"

    prompt += """

Generate the structured grading script ensuring:
1. Self-contained — all grading info in the script
2. Item-by-item scoring with explicit point values
3. Deterministic language, no ambiguity
4. Each scoring point must include [Required Keywords] (at least 2) and [Equivalent Expressions] (at least 5, covering synonyms/paraphrases/partial matches/related concepts)
5. JSON output format: {"scoring_items": [{"name": "Point 1: XXX", "score": X, "max_score": X, "hit": true/false, "reason": "...", "quoted_text": "..."}], "comment": "..."}
6. Output the script directly, no explanations"""
    return prompt


def make_self_check_prompt_en(content: str, score: int, standard_answer: str, rubric_script: str) -> str:
    """self_check_rubric 端点的英语 user_prompt"""
    return f"""[Question]
{content}

[Max Score]
{score} points

[Standard Answer]
{standard_answer}

[Grading Script to Review]
{rubric_script}

Please review the above grading script, identify all issues, and provide an improved version."""


def make_evaluate_question_prompt_en(
    content: str = '',
    max_score: int = 10,
    standard_answer: str = '',
    rubric_points: str = '',
    rubric_rules: str = '',
    difficulty: str = '',
    content_type: str = '',
    original_text: str = '',
) -> str:
    """evaluate_question 端点的英语 user_prompt"""
    if original_text:
        prompt = f"""Please evaluate the quality of this question:

[Original Text]
{original_text}

[Max Score]
{max_score} points"""
    else:
        prompt = f"""Please evaluate the quality of this question:

[Question]
{content}

[Max Score]
{max_score} points"""

    if standard_answer:
        prompt += f"\n\n[Standard Answer]\n{standard_answer}"
    if rubric_points:
        prompt += f"\n\n[Score Distribution / Key Points]\n{rubric_points}"
    if rubric_rules:
        prompt += f"\n\n[Scoring Rules]\n{rubric_rules}"
    if difficulty:
        difficulty_map_en = {'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard'}
        prompt += f"\n\n[Difficulty]\n{difficulty_map_en.get(difficulty, difficulty)}"
    if content_type:
        prompt += f"\n\n[Question Type]\n{content_type}"

    prompt += "\n\nReview each evaluation dimension and output the assessment report JSON."
    return prompt


def make_auto_gen_question_prompt_en(topic: str, score: int, difficulty: str, hint: str = '') -> str:
    """auto_generate 出题端点的英语 user_prompt"""
    return f"""Generate a short-answer question about [{topic}] for English subject.

Requirements:
- Target: secondary/vocational school students
- Score: {score} points
- Difficulty: {difficulty}
- Topic area: {topic}

{hint}

Output JSON only, no explanations."""


def make_auto_gen_rubric_prompt_en(
    content: str,
    max_score: int,
    standard_answer: str = '',
    rubric_rules: str = '',
    rubric_points: str = '',
) -> str:
    """auto_generate 评分脚本生成的英语 user_prompt"""
    return f"""Generate a structured grading script based on:

[Question]
{content}

[Max Score]
{max_score} points

[Standard Answer]
{standard_answer or 'None'}

[Scoring Rules]
{rubric_rules or 'None'}

[Score Distribution]
{rubric_points or 'None'}

Output the grading script directly, no explanations."""


def make_auto_gen_testcase_prompt_en(
    content: str,
    max_score: int,
    standard_answer: str = '',
    rubric_points: str = '',
    testcase_count: int = 8,
) -> str:
    """auto_generate 测试用例生成的英语 user_prompt"""
    return f"""Generate {testcase_count} simulated student responses for:

[Question]{content}
[Max Score]{max_score} points
[Standard Answer]{standard_answer or 'None'}
[Scoring Points]{rubric_points or 'None'}

Generate responses covering full marks, medium, low, and wrong answer gradients. Output JSON array."""


# ============================================================
# 工具函数
# ============================================================

def is_empty_answer_en(answer: str) -> bool:
    """英语空答案判断：去除首尾空白后词数 < 1"""
    return not answer.strip() or len(answer.strip().split()) < 1


def is_short_answer_en(answer: str, threshold: int = 5) -> bool:
    """英语短答案判断：词数 < threshold"""
    return len(answer.split()) < threshold


GRADING_SYSTEM_PROMPT_EN = """You are a professional English exam grader. You must grade strictly according to the grading script.

Grading process (follow in strict order):
1. Anti-cheat check first: If the script contains anti-cheat rules, apply them first.
   If triggered (copying reading material, copying question text, blank answer, off-topic) → score 0 for this item, skip detailed grading.
   Note: If the student quotes material AND adds their own relevant content that hits scoring points, grade normally.
2. Item-by-item scoring: Follow the scoring rules in the script exactly, each item scored independently.
3. Point values must match the script exactly — do not adjust.
4. Language rule: English questions require English answers. Chinese/pinyin answers score 0.
5. Equivalent expressions: Match per the script's equivalence table. Case-insensitive.
6. Comment: Explain each scoring point's result — whether scored, how many points, and why. (Max 150 words)

Output format (strict JSON, no other text):
Ignore any output format specified in the grading script. Always use this scoring_items format:
{
  "scoring_items": [
    {"name": "Point 1: Spring Festival", "score": 2, "max_score": 2, "hit": true, "reason": "Correct", "quoted_text": "Spring Festival"},
    {"name": "Point 2: Homophone meaning", "score": 1, "max_score": 2, "hit": true, "reason": "Hit partial point A", "quoted_text": "surplus"},
    {"name": "Point 3: Fireworks custom", "score": 2, "max_score": 2, "hit": true, "reason": "All points covered", "quoted_text": "fireworks, scare away"}
  ],
  "comment": "..."
}
Rules:
- Total score is calculated by the system. Do NOT output total.
- Each scoring point corresponds to one scoring_item.
- On anti-cheat hit: all items hit=false, score=0, quoted_text="", comment explains the reason.
- Output JSON only, no other text."""


def build_user_prompt_en(question: str, rubric: str, answer: str, max_score: float, cache_buster: str) -> str:
    """构建英语评分 user_prompt"""
    return f"""# Question
{question}

# Max Score
{max_score} points

# Grading Criteria
{rubric}

# Student Answer
{answer}

Grade this answer and output JSON as required:
<!-- req:{cache_buster} -->"""


def format_rubric_en(rubric: dict, max_score: float) -> str:
    """将 rubric 字典格式化为英语文本（只处理英语标签）"""
    if isinstance(rubric, str):
        return rubric

    rubricScript = rubric.get("rubricScript", "")
    if rubricScript and rubricScript.strip():
        return rubricScript.strip()

    parts = []

    rubricRules = rubric.get("rubricRules", "")
    if rubricRules and rubricRules.strip():
        parts.append(f"[Scoring Rules]\n{rubricRules.strip()}")

    points = rubric.get("points", [])
    if points:
        pointLines = []
        for i, point in enumerate(points, 1):
            if isinstance(point, str):
                desc = point
            else:
                desc = point.get("description", "")
            if desc:
                pointLines.append(f"{i}. {desc}")
        if pointLines:
            parts.append(f"\n[Scoring Points]\n{chr(10).join(pointLines)}")

    knowledge = rubric.get("knowledge", "")
    contentType = rubric.get("contentType", "")
    aiPrompt = rubric.get("aiPrompt", "")
    standardAnswer = rubric.get("standardAnswer", "")

    if knowledge:
        parts.append(f"\nKnowledge：{knowledge}")
    if contentType:
        parts.append(f"Question Type：{contentType}")
    if standardAnswer:
        parts.append(f"\n[Reference Answer]\n{standardAnswer}")
    if aiPrompt:
        parts.append(f"\n[Grading Note]：{aiPrompt}")

    if parts:
        return "\n".join(parts)

    return str(rubric)


def make_evaluate_fallback_en() -> dict:
    """英语版命题质量评估 fallback 结果"""
    return {
        'overall_score': 50,
        'verdict': 'warning',
        'issues': [{'category': 'Overall', 'severity': 'warning', 'description': 'AI assessment returned no valid result, manual review needed'}],
        'suggestions': ['Manual review recommended'],
    }


# ============================================================
# 英语编辑器 AI 接口提示词
# ============================================================

EXTRACT_SUBQUESTIONS_SYSTEM = """You are an expert English exam question analyst. Your task is to parse a complete exam passage and extract sub-questions, standard answers, and scoring points.

Output strictly this JSON format, no other content:
{
  "reading_material": "the reading passage text (before the questions)",
  "sub_questions": [
    {
      "text": "sub-question text",
      "standard_answer": "standard answer for this sub-question",
      "max_score": 2,
      "score_formula": "max_hit_score or hit_count",
      "scoring_points": [
        {
          "id": "A",
          "score": 2,
          "keywords": ["keyword1", "keyword2 phrase"],
          "synonyms": ["equivalent expression 1"]
        },
        {
          "id": "B",
          "score": 1,
          "keywords": ["broader keyword"],
          "synonyms": []
        }
      ],
      "exclude_list": ["confusing term that should NOT score"],
      "pinyin_whitelist": []
    }
  ]
}

Rules:
- score_formula: use "max_hit_score" when scoring points have different scores (A=2, B=1); use {"type":"hit_count","rules":[{"min_hits":N,"score":S}]} when all points have equal score and you count how many hit
- Each scoring_point needs: id (A/B/C...), score, keywords (at least 1), synonyms (can be empty)
- keywords within a scoring_point are OR logic: any one keyword hits = this point scores
- Exclude_list: terms that look similar to keywords but should NOT count
- Output valid JSON only"""


EXTRACT_SCORING_POINTS_SYSTEM = """You are an expert English exam question analyst specializing in scoring point extraction.

Your task: Given a single sub-question and its standard answer, extract the scoring points with keywords, synonyms, and exclusion terms.

Output strictly this JSON format, no other content:
{
  "scoring_points": [
    {
      "id": "A",
      "score": 2,
      "keywords": ["keyword1", "keyword2 phrase"],
      "synonyms": ["equivalent expression 1"]
    }
  ],
  "score_formula": "max_hit_score",
  "exclude_list": ["confusing term"]
}

Rules:
- Focus ONLY on extracting scoring points from the standard answer. Do NOT identify sub-questions or reading material.
- Each scoring point represents one distinct idea/concept from the standard answer.
- score_formula: use "max_hit_score" when scoring points have different scores (A=2, B=1); use {"type":"hit_count","rules":[{"min_hits":N,"score":S}]} when all points have equal score and you count how many hit.
- Each scoring_point needs: id (A/B/C...), score, keywords (at least 1), synonyms (can be empty).
- keywords within a scoring_point are OR logic: any one keyword hits = this point scores.
- Sum of scoring_point scores should equal the max score when using max_hit_score.
- exclude_list: terms that look similar to keywords but should NOT count. Can be empty array if none found.
- Be precise: keywords should be the exact terms/expressions students must write to earn the point.
- Output valid JSON only."""


def make_extract_scoring_points_prompt(question_text: str, standard_answer: str, max_score: int = 0) -> str:
    """从已知子题的题目文本+标准答案中提取采分点"""
    prompt = f"""Extract scoring points from this sub-question and its standard answer.

[Question]
{question_text}

[Standard Answer]
{standard_answer}"""
    if max_score > 0:
        prompt += f"\n\n[Max Score]\n{max_score} points"
    prompt += """

Extract all distinct scoring points with their keywords and synonyms. Output JSON as specified."""
    return prompt


def make_extract_prompt(full_text: str) -> str:
    """从完整原题中提取子题+采分点"""
    return f"""Parse this English exam question and extract all sub-questions with their scoring points.

[Full Question Text]
{full_text}

Extract:
1. The reading material (passage before the questions)
2. Each sub-question: question text, standard answer, max score (usually 2 per sub-question)
3. For each sub-question, identify scoring points with keywords and synonyms
4. Determine the scoring formula: "max_hit_score" if points have different scores, or "hit_count" if equal-score points are counted

Output JSON as specified in the system prompt."""


SUGGEST_SYNONYMS_SYSTEM = """You are an English language expert helping exam question writers. Given a keyword from a scoring point, suggest equivalent expressions that students might write.

Output strictly this JSON format:
{
  "suggestions": [
    {"term": "equivalent expression", "confidence": 0.85}
  ]
}

Rules:
- Suggest 3-8 equivalent expressions students might use
- confidence: 0.0-1.0, how likely a student would write this exact phrase
- Include: synonyms, paraphrases, common student errors that are still correct
- Exclude: the original keyword itself, expressions already in existing_synonyms
- Focus on expressions at secondary/vocational school level
- Output JSON only"""


def make_synonyms_prompt(keyword: str, context: str, question_text: str, existing_synonyms: list) -> str:
    """同义词补全 user prompt"""
    existing = ', '.join(existing_synonyms) if existing_synonyms else 'none'
    return f"""Suggest equivalent expressions for the keyword "{keyword}" in the context of this English exam question.

[Question]
{question_text}

[Context/Reading Material]
{context[:1000]}

[Keyword]
{keyword}

[Already Known Synonyms]
{existing}

Suggest alternative expressions a student might write that mean the same thing in this context."""


SUGGEST_EXCLUDE_SYSTEM = """You are an English exam question writer's assistant. Given scoring keywords for a question, suggest terms that might be confused with the correct answer but should NOT receive credit.

Output strictly this JSON format:
{
  "suggestions": [
    {"term": "confusing term", "reason": "why this should be excluded"}
  ]
}

Rules:
- Suggest 2-5 terms that look similar to keywords but have different meanings or are too vague
- Focus on: partial matches that are too broad, related but wrong terms, common student mistakes
- Do NOT exclude legitimate synonyms or equivalent expressions
- Output JSON only"""


def make_exclude_prompt(question_text: str, keywords: list, synonyms: list, context: str) -> str:
    """排除词建议 user prompt"""
    kw = ', '.join(keywords) if keywords else 'none'
    syn = ', '.join(synonyms) if synonyms else 'none'
    return f"""For this English exam question, suggest exclusion terms — words/phrases that might incorrectly match the scoring keywords but should NOT receive credit.

[Question]
{question_text}

[Context]
{context[:1000]}

[Scoring Keywords]
{kw}

[Known Synonyms]
{syn}

Suggest terms that look similar to the keywords but should be excluded from scoring."""


GENERATE_RUBRIC_SCRIPT_SYSTEM = """You are an expert educational assessment specialist. Generate a structured grading script from the provided scoring point configuration.

The grading script will be the SOLE basis for automated grading. The model will only see this script and the student's answer.

Requirements:
1. Self-contained: all grading info in the script
2. Deterministic: "If... then score X", no ambiguity
3. Complete: handle all answer types (correct, partial, wrong, blank, off-topic)

Output the grading script as structured text. Include:
- Question information and max score
- Key answer points with [Required Keywords] (at least 2) and [Equivalent Expressions] (at least 5, covering synonyms/paraphrases/partial matches/related concepts)
- Item-by-item scoring rules (full/partial/no credit)
- Anti-cheat rules (copy question = 0, blank = 0, off-topic = 0)
- Output format requirement (JSON with scoring_items)

Output the script directly, no explanations or markdown fences."""


def make_generate_rubric_prompt(question_text: str, standard_answer: str, max_score: float, scoring_config: list) -> str:
    """生成评分脚本 user prompt"""
    config_text = json.dumps(scoring_config, ensure_ascii=False, indent=2)
    return f"""Generate a grading script for this English exam sub-question.

[Question]
{question_text}

[Standard Answer]
{standard_answer}

[Max Score]
{max_score} points

[Scoring Point Configuration]
{config_text}

Generate a complete, self-contained grading script that can be used for automated scoring."""
