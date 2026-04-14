#!/usr/bin/env python3
"""
回填子题的 standard_answer

从 question_answers 表的 answer_text (JSON) 中提取关键词+同义词，
组装为可读的标准答案文本，更新到 questions 表的 standard_answer 列。

处理范围：所有 parent_id IS NOT NULL 的子题。
幂等设计：仅更新 standard_answer 为空的子题。

用法：
    python scripts/backfill_standard_answer.py          # dry-run，仅打印
    python scripts/backfill_standard_answer.py --apply   # 实际写入
"""
import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.db_models import get_db_connection


def build_standard_answer(answer_json: dict) -> str:
    """
    从采分点 JSON 构建标准答案文本。

    格式示例：
        A: spring festival (keywords: spring festival; synonyms: -) [2分]
        B: spring, festival (keywords: spring, festival; synonyms: -) [1分]

    max_hit_score 公式：取命中最高分的采分点
    hit_count 公式：按命中数累计
    """
    scoring_points = answer_json.get("scoring_points", [])
    score_formula = answer_json.get("score_formula", "max_hit_score")

    if not scoring_points:
        return ""

    lines = []
    for sp in scoring_points:
        sp_id = sp.get("id", "")
        score = sp.get("score", 0)
        keywords = sp.get("keywords", [])
        synonyms = sp.get("synonyms", [])

        kw_str = ", ".join(keywords) if keywords else "-"
        syn_str = ", ".join(synonyms) if synonyms else "-"

        lines.append(f"{sp_id}: keywords=[{kw_str}]; synonyms=[{syn_str}] [{score}分]")

    # 标注计分公式
    if isinstance(score_formula, dict):
        formula_type = score_formula.get("type", "hit_count")
    else:
        formula_type = str(score_formula)

    formula_label = {
        "max_hit_score": "取命中最高分",
        "hit_count": "按命中数累计",
    }.get(formula_type, formula_type)

    return f"计分方式: {formula_label}\n" + "\n".join(lines)


def main():
    apply = "--apply" in sys.argv
    conn = get_db_connection()
    cursor = conn.cursor()

    # 查询所有子题及其对应的 scoring_point 答案
    cursor.execute("""
        SELECT q.id, q.title, q.standard_answer, qa.answer_text
        FROM questions q
        JOIN question_answers qa ON q.id = qa.question_id AND qa.scope_type = 'scoring_point'
        WHERE q.parent_id IS NOT NULL
        ORDER BY q.parent_id, q.id
    """)
    rows = cursor.fetchall()

    updated = 0
    skipped_has_data = 0
    skipped_no_answer = 0

    for row in rows:
        q_id, title, current_std_answer, answer_text = row

        # 跳过已有 standard_answer 的
        if current_std_answer and current_std_answer.strip():
            skipped_has_data += 1
            print(f"  SKIP (已有数据) id={q_id} title={title}")
            continue

        if not answer_text:
            skipped_no_answer += 1
            print(f"  SKIP (无answer_text) id={q_id} title={title}")
            continue

        try:
            answer_json = json.loads(answer_text)
        except json.JSONDecodeError:
            print(f"  ERROR JSON解析失败 id={q_id} title={title}")
            continue

        new_std_answer = build_standard_answer(answer_json)
        if not new_std_answer:
            print(f"  SKIP (无采分点) id={q_id} title={title}")
            continue

        print(f"  UPDATE id={q_id} title={title}")
        print(f"    -> {new_std_answer[:80]}...")

        if apply:
            cursor.execute(
                "UPDATE questions SET standard_answer = ? WHERE id = ?",
                (new_std_answer, q_id),
            )
            updated += 1

    if apply:
        conn.commit()
        print(f"\n已提交: {updated} 条更新")
    else:
        print(f"\n[DRY-RUN] 将更新 {len(rows) - skipped_has_data - skipped_no_answer} 条")
        print(f"  跳过(已有数据): {skipped_has_data}")
        print(f"  跳过(无answer_text): {skipped_no_answer}")
        print("加 --apply 参数实际写入")

    conn.close()


if __name__ == "__main__":
    main()
