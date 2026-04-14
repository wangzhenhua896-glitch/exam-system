#!/usr/bin/env python3
"""导入英语简答题第1题（Li Ming 阅读理解）到数据库"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.db_models import get_db_connection


def main():
    # 阅读材料
    passage = (
        "My name is Li Ming. I'm a student at a vocational school in Beijing. "
        "I study computer science and I really enjoy it. Every morning, I get up "
        "at 6:30 and go to school by subway. It takes about 30 minutes.\n\n"
        "After school, I usually go to the library to study or do my homework. "
        "Sometimes, I play basketball with my friends in the gym. On weekends, I "
        "often visit my grandparents. They live in a small town near Beijing. I "
        "help them with housework and we have dinner together.\n\n"
        "I like my school life very much. My teachers are very kind and my "
        "classmates are friendly. We often help each other with our studies."
    )

    # 3 道子题
    children = [
        {
            "question": "What does Li Ming study at the vocational school?",
            "max_score": 2.0,
            "standard_answer": "Computer science.",
        },
        {
            "question": "How does Li Ming go to school every day?",
            "max_score": 2.0,
            "standard_answer": "By subway.",
        },
        {
            "question": "What does Li Ming do on weekends?",
            "max_score": 2.0,
            "standard_answer": "He visits his grandparents.",
        },
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查是否已导入（按题号去重）
    cursor.execute("SELECT id FROM questions WHERE question_number = '13' AND parent_id IS NULL")
    if cursor.fetchone():
        print("题号 13 已存在，跳过导入。")
        conn.close()
        return

    # 1. 插入父题
    total_score = sum(c["max_score"] for c in children)
    cursor.execute(
        '''INSERT INTO questions
           (subject, title, content, original_text, standard_answer,
            rubric_rules, rubric_points, rubric_script, rubric, max_score,
            question_number, difficulty, exam_name, parent_id)
           VALUES (?, ?, ?, ?, '', '', '', '', '{}', ?, ?, 'medium', '4.2普测简答题', NULL)''',
        (
            'english',
            passage[:30],
            passage,
            passage,
            total_score,
            '13',
        ),
    )
    parent_id = cursor.lastrowid
    print(f"父题已插入: id={parent_id}, max_score={total_score}")

    # 2. 插入子题 + 标准答案
    for i, child in enumerate(children, 1):
        cursor.execute(
            '''INSERT INTO questions
               (subject, title, content, original_text, standard_answer,
                rubric_rules, rubric_points, rubric_script, rubric, max_score,
                question_number, difficulty, exam_name, parent_id)
               VALUES (?, ?, ?, ?, ?, '', '', '', '{}', ?, ?, 'medium', '4.2普测简答题', ?)''',
            (
                'english',
                child["question"][:30],
                child["question"],
                child["question"],
                child["standard_answer"],
                child["max_score"],
                f'13.{i}',
                parent_id,
            ),
        )
        child_id = cursor.lastrowid
        print(f"  子题 {i} 已插入: id={child_id}, question_number=13.{i}")

        # 插入标准答案到 question_answers
        cursor.execute(
            '''INSERT INTO question_answers
               (question_id, scope_type, scope_id, score_ratio, answer_text, label, source)
               VALUES (?, 'question', '', 1.0, ?, '标准答案', 'manual')''',
            (child_id, child["standard_answer"]),
        )
        print(f"    标准答案已插入: {child['standard_answer']}")

    conn.commit()
    conn.close()
    print("\n导入完成！")


if __name__ == '__main__':
    main()
