# 英语 LLM 兜底方案设计

> 版本：v1.0.0 | 日期：2026-04-13 | 分支：multi-fullscore-answers

## 1. 核心原则

精确匹配和 LLM 兜底**共用同一份采分点 JSON 数据**，只是匹配方式不同：
- 精确匹配：字符串子串包含 → 确定性给分
- LLM 兜底：语义等价判断 → LLM 给分

**关键约束**：LLM 只能决定"是否命中采分点"，不能创造采分点之外的给分理由。

## 2. 两层关系

```
学生答案
  ↓
第1层：精确匹配采分点 keywords/synonyms（归一化后子串包含）
  ├─ 命中（score > 0）→ 直接返回，不调 LLM，模板化评语
  └─ 未命中（score = 0）→ 进入第3层 LLM 兜底
        ↓
      第3层：LLM 用采分点 JSON 判断语义等价
        ├─ 语义等价命中某采分点 → 按该采分点 score 给分
        ├─ 语义上正确但不匹配任何采分点 → 0 分
        ├─ 答非所问/拼音/汉字 → 0 分
        └─ 输出：scoring_items + comment
```

## 3. 评分数据源统一

| 层 | 数据源 | 匹配方式 |
|----|--------|---------|
| 第1层（精确匹配） | 采分点 JSON | 字符串子串包含 |
| 第3层（LLM 兜底） | 采分点 JSON（同一份） | LLM 语义判断 |

**不再使用**：原有的 rubric_script 作为 LLM 输入。采分点 JSON 是英语评分的唯一依据。

## 4. LLM 兜底 Prompt 设计

### 4.1 System Prompt

```
You are a professional English exam grader. Your job is to determine whether
the student's answer semantically matches any scoring point.

Rules:
1. Check each scoring point's keywords and synonyms against the student answer.
   A match means the student's answer conveys the same meaning, even if the
   exact words differ.
2. If the answer matches a scoring point semantically, award that point's score.
3. If the answer is correct in meaning but does NOT match any scoring point,
   score 0 (scoring points are the only grading basis).
4. If the answer is off-topic, in Chinese, or in pinyin, score 0.
5. Extra correct information does not reduce the score.
6. Output JSON only, no other text.
```

### 4.2 User Prompt 构造

```python
def build_english_fallback_prompt(question, answer, sp_json, max_score):
    scoring_points_text = format_scoring_points(sp_json)
    # sp_json 包含：sub_question text, scoring_points[], score_formula, exclude_list

    return f"""# Question
{question}

# Max Score
{max_score} points

# Scoring Points
{scoring_points_text}

# Exclude List (score 0 if matched)
{sp_json.get('exclude_list', [])}

# Student Answer
{answer}

Determine if the student's answer semantically matches any scoring point.
Output JSON:
{{
  "scoring_items": [
    {{"name": "Point A: [keyword]", "score": 2, "max_score": 2, "hit": true, "reason": "Semantic match", "quoted_text": "relevant text from answer"}}
  ],
  "comment": "..."
}}
Total score is calculated by the system. Do NOT output total.
Output JSON only."""
```

### 4.3 采分点 JSON 格式化为 Prompt 文本

```python
def format_scoring_points(sp_json):
    lines = []
    for sp in sp_json['scoring_points']:
        kw = ', '.join(sp['keywords'])
        syn = ', '.join(sp.get('synonyms', []))
        line = f"- {sp['id']} ({sp['score']}pt): {kw}"
        if syn:
            line += f" | Equivalent: {syn}"
        lines.append(line)

    formula = sp_json.get('score_formula')
    if isinstance(formula, str) and formula == 'max_hit_score':
        lines.append("Strategy: Award the highest matching score.")
    elif isinstance(formula, dict) and formula.get('type') == 'hit_count':
        rules = formula['rules']
        rules_text = ', '.join(f"{r['min_hits']} hits → {r['score']}pt" for r in rules)
        lines.append(f"Strategy: Count hits, then lookup: {rules_text}")

    return '\n'.join(lines)
```

## 5. 代码实现

### 5.1 qwen_engine.py 新增方法

```python
async def grade_english_fallback(
    self,
    question: str,
    answer: str,
    scoring_point_json: Dict[str, Any],
    max_score: float,
) -> QwenGradingResult:
    """
    英语 LLM 兜底评分

    精确匹配未命中时，用采分点 JSON 构造 prompt 让 LLM 判断语义等价。
    采分点 JSON 是唯一评分依据，LLM 不能创造采分点之外的给分理由。
    """
    system_prompt = self._get_english_fallback_system_prompt()
    user_prompt = self._build_english_fallback_prompt(
        question, answer, scoring_point_json, max_score
    )
    # ... 调用 LLM，解析输出（复用现有 _parse_output 逻辑）
```

### 5.2 three_layer_grader.py 修改

```python
async def three_layer_grade(...):
    if subject == 'english':
        # 第1层：精确匹配
        sp_row = find_scoring_point_row(question_answers)
        sp_json = json.loads(sp_row['answer_text']) if sp_row else None

        if sp_json:
            sp_score, sp_detail = english_scoring_point_match(answer, sp_json, max_score)
            layer_scores['keyword'] = sp_score
            layer_details['keyword'] = sp_detail

            if sp_score > 0:
                # 命中，跳过 LLM
                return {
                    'final_score': sp_score,
                    'strategy': 'max',
                    'layer_scores': layer_scores,
                    'layer_details': layer_details,
                    'llm_result': None,
                }

        # 第1层 miss，LLM 兜底
        llm_result = await grading_engine.grade_english_fallback(
            question=question,
            answer=answer,
            scoring_point_json=sp_json,
            max_score=max_score,
        )
        layer_scores['llm'] = llm_result.final_score
        # 策略：max(A=0, C) = C
        final_score = _apply_strategy(layer_scores, 'max')
        return ...
```

## 6. 与现有方案的区别

| 维度 | 现状（纯 LLM） | 新方案（精确匹配 + LLM 兜底） |
|------|----------------|---------------------------|
| LLM 输入 | rubric_script（通用评分脚本） | 采分点 JSON（结构化数据） |
| LLM 职责 | 完整评分（逐项判断+给分+评语） | 仅判断语义等价（是否命中采分点） |
| LLM 调用频率 | 每题必调 | 仅精确 miss 时调用（预期 <20%） |
| 评分依据 | LLM 自由发挥 | 采分点 JSON 是唯一依据 |
| 可解释性 | 弱（LLM 评语可能模糊） | 强（命中/未命中明确指向采分点） |

## 7. 边界情况汇总

| 场景 | 第1层（精确匹配） | 第3层（LLM兜底） | 最终得分 |
|------|-----------------|-----------------|---------|
| `The Spring Festival` | 命中A，2分 | 不调用 | 2分 |
| `Spring` | 命中B，1分 | 不调用 | 1分 |
| `They celebrate the spring festival` | 命中A，2分 | 不调用 | 2分 |
| `lunar new year` | 排除列表命中，0分 | 不调用 | 0分 |
| `the celebration of the spring fest` | miss（拼写不完整） | LLM判断语义等价→2分 | 2分 |
| `because fish is delicious`（Q2） | miss | LLM判断答非所问→0分 | 0分 |
| `chang'e flew to the moon`（Q3） | miss（精确匹配未覆盖） | LLM判断语义等价→2分 | 2分 |
| `春节` | CJK检测，0分 | 不调用 | 0分 |
| `Chun Jie` | 拼音检测，0分 | 不调用 | 0分 |

## 8. 后续优化方向

1. **采分点覆盖率提升**：统计 LLM 兜底频次，如果某采分点频繁被 LLM 命中但精确匹配 miss，补充同义表达到 synonyms
2. **LLM 兜底结果缓存**：同一学生答案 + 同一采分点 JSON 的 LLM 结果缓存，避免重复调用
3. **语义放松标记**：采分点 JSON 中增加 `semantic_relaxation: true` 标记（如嫦娥奔月），前端提示"此采分点支持语义匹配"
