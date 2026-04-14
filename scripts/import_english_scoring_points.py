#!/usr/bin/env python3
"""
导入英语采分点数据

为 6 道英语题创建子题（Q1/Q2/Q3）和结构化采分点 JSON 数据。
幂等设计：已存在则更新，不存在则插入。

用法：
    python scripts/import_english_scoring_points.py
"""
import sys
import os
import json
import sqlite3

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.db_models import get_db_connection

# ─── 采分点数据定义 ───────────────────────────────────────────────

QUESTIONS_DATA = [
    {
        "question_number": "0001",
        "parent_id": 166,
        "title_prefix": "Chinese New Year",
        "pinyin_whitelist": [],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "What is the other name of Chinese New Year?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": ["new year", "lunar new year"],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["spring festival"],
                        "synonyms": []
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["spring", "festival"],
                        "synonyms": []
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "Why do families serve fish during the reunion dinner?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["sounds like surplus"],
                        "synonyms": ["sounds similar to surplus", "means surplus"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["yearly prosperity"],
                        "synonyms": ["prosperity every year", "abundance", "more than enough"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "How do people welcome the new year at midnight on New Year's Eve?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["light fireworks"],
                        "synonyms": ["set off fireworks", "fireworks display", "shoot off fireworks", "light up fireworks"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["scare away evil spirits"],
                        "synonyms": ["drive away bad luck", "chase away evil", "frighten evil spirits"]
                    }
                ]
            }
        ]
    },
    {
        "question_number": "0002",
        "parent_id": 167,
        "title_prefix": "Dragon Boat Festival",
        "pinyin_whitelist": ["zongzi"],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "When is Dragon Boat Festival celebrated?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["5th day of the 5th lunar month"],
                        "synonyms": ["the fifth day of the fifth lunar month", "the 5th lunar month's 5th day"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["june"],
                        "synonyms": ["in june", "the month of june"]
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "What is the most important food during Dragon Boat Festival?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": [],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["zongzi"],
                        "synonyms": []
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["rice dumpling"],
                        "synonyms": ["sticky rice wrapped in bamboo leaves"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "Why do people hold dragon boat races and eat zongzi?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["remember"],
                        "synonyms": ["honor", "commemorate", "in memory of"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["qu yuan"],
                        "synonyms": []
                    }
                ]
            }
        ]
    },
    {
        "question_number": "0003",
        "parent_id": 168,
        "title_prefix": "The Mid-Autumn Festival",
        "pinyin_whitelist": [],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "When is the Mid-Autumn Festival celebrated?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["15th day of the 8th lunar month"],
                        "synonyms": ["the fifteenth day of the eighth lunar month", "the 8th lunar month's 15th day"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["september or early october"],
                        "synonyms": ["september or october", "sept. or early oct.", "september", "october"]
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "How do people celebrate the Mid-Autumn Festival?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["share mooncakes"],
                        "synonyms": ["eat mooncakes", "have mooncakes"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["admire the full moon"],
                        "synonyms": ["gaze at the moon", "enjoy the bright moon", "watch the moon"]
                    },
                    {
                        "id": "C", "score": 1,
                        "keywords": ["enjoy time with family"],
                        "synonyms": ["spend time with family", "family reunion", "get together"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "What is the most famous story about The Mid-Autumn Festival?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": [],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["chang'e flying to the moon"],
                        "synonyms": ["chang'e flew to the moon"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["chang'e"],
                        "synonyms": ["the jade rabbit"]
                    }
                ]
            }
        ]
    },
    {
        "question_number": "0004",
        "parent_id": 169,
        "title_prefix": "The Great Wall of China",
        "pinyin_whitelist": [],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "When was the Great Wall first built?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": [],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["2000 years ago"],
                        "synonyms": ["2,000 years ago", "over two thousand years ago", "over 2,000 years ago", "more than 2,000 years ago", "about 2,000 years ago"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["2000 years"],
                        "synonyms": ["2,000 years", "two thousand years", "over 2,000", "more than 2,000"]
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "What materials were used to build the Great Wall?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["stone"],
                        "synonyms": ["stones"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["brick"],
                        "synonyms": ["bricks"]
                    },
                    {
                        "id": "C", "score": 1,
                        "keywords": ["earth"],
                        "synonyms": ["soil", "mud"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "Why was the Great Wall built?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["protect china from invaders"],
                        "synonyms": ["defend china from attacks", "keep invaders out", "protect against enemies", "stop invaders", "protect the country from invasion"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["control trade"],
                        "synonyms": ["control trade along the silk road", "manage trade routes", "control commerce", "regulate trade"]
                    }
                ]
            }
        ]
    },
    {
        "question_number": "0005",
        "parent_id": 170,
        "title_prefix": "High-Speed Rail in China",
        "pinyin_whitelist": [],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "In which country does high-speed rail play an important role in daily life?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": [],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["china"],
                        "synonyms": ["chinese high-speed rail", "the country of china"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["chsr"],
                        "synonyms": ["CHSR"]
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "What are some key benefits of high-speed rail?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["connects remote communities"],
                        "synonyms": ["connecting remote communities", "improving accessibility", "links remote areas", "connectivity to remote areas"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["promotes economic development"],
                        "synonyms": ["balanced regional economic development", "economic growth", "promotes economic growth", "stimulates economic development"]
                    },
                    {
                        "id": "C", "score": 1,
                        "keywords": ["reduces traffic congestion on roads"],
                        "synonyms": ["reduces traffic congestion", "relieves traffic pressure", "reducing traffic", "easing road congestion", "reduces pressure on existing transport"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "What are some challenges associated with high-speed rail?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["noise"],
                        "synonyms": ["land use", "land acquisition", "environmental impact", "environmental concerns", "affects communities", "disrupts communities", "comfort", "vibration"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["safety"],
                        "synonyms": ["safety risks", "accidents", "dangers", "safety hazards", "risk of accidents", "safety concerns", "operational risks"]
                    }
                ]
            }
        ]
    },
    {
        "question_number": "0006",
        "parent_id": 171,
        "title_prefix": "Chinese Tea Culture",
        "pinyin_whitelist": [],
        "sub_questions": [
            {
                "sub_id": "Q1",
                "text": "What is Longjing tea?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "max_hit_score",
                "exclude_list": [],
                "scoring_points": [
                    {
                        "id": "A", "score": 2,
                        "keywords": ["green tea"],
                        "synonyms": ["a green tea", "green tea leaves", "a kind of green tea", "it is green tea"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["tea"],
                        "synonyms": []
                    }
                ]
            },
            {
                "sub_id": "Q2",
                "text": "How is tea prepared in a traditional tea ceremony?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["with care"],
                        "synonyms": ["carefully", "in a careful way"]
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["special teapots, cups, and tools"],
                        "synonyms": ["special teapots and cups", "special tools and teapots", "teapots and cups", "cups and tools"]
                    }
                ]
            },
            {
                "sub_id": "Q3",
                "text": "What values does tea culture reflect?",
                "max_score": 2,
                "scoring_strategy": "max",
                "score_formula": "hit_count",
                "exclude_list": [],
                "scoring_rules": [
                    {"min_hits": 2, "score": 2},
                    {"min_hits": 1, "score": 1}
                ],
                "scoring_points": [
                    {
                        "id": "A", "score": 1,
                        "keywords": ["harmony"],
                        "synonyms": []
                    },
                    {
                        "id": "B", "score": 1,
                        "keywords": ["patience"],
                        "synonyms": []
                    },
                    {
                        "id": "C", "score": 1,
                        "keywords": ["hospitality"],
                        "synonyms": []
                    }
                ]
            }
        ]
    }
]


def find_existing_child(cursor, parent_id: int, sub_id: str) -> dict | None:
    """查找已存在的子题（按 parent_id + question_number 匹配）"""
    cursor.execute(
        'SELECT * FROM questions WHERE parent_id = ? AND question_number = ?',
        (parent_id, sub_id)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def find_existing_scoring_point(cursor, child_id: int, sub_id: str) -> dict | None:
    """查找已存在的采分点行（按 question_id + scope_id 匹配，每个子题一行）"""
    cursor.execute(
        'SELECT * FROM question_answers WHERE question_id = ? AND scope_type = ? AND scope_id = ?',
        (child_id, 'scoring_point', sub_id)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def build_sub_question_rubric(sub_q: dict) -> str:
    """构建子题的评分配置 JSON（存入 rubric 字段）"""
    config = {
        "scoring_strategy": sub_q["scoring_strategy"],
        "exclude_list": sub_q.get("exclude_list", []),
        "pinyin_whitelist": sub_q.get("pinyin_whitelist", []),
        "scoring_points": sub_q["scoring_points"]
    }
    if sub_q.get("scoring_rules"):
        config["scoring_rules"] = sub_q["scoring_rules"]
    return json.dumps(config, ensure_ascii=False)


def build_scoring_point_json(sub_q: dict, pinyin_whitelist: list) -> str:
    """构建完整的子题采分点 JSON（存入 question_answers.answer_text）

    与 english_scoring_point_match() 函数的输入格式一致：
    {
        "id": "Q1",
        "text": "问题文本",
        "max_score": 2,
        "scoring_points": [...],
        "score_formula": "max_hit_score" 或 {"type": "hit_count", "rules": [...]},
        "exclude_list": [...],
        "pinyin_whitelist": [...]
    }
    """
    score_formula = sub_q["score_formula"]
    if score_formula == "hit_count":
        score_formula = {
            "type": "hit_count",
            "rules": sub_q.get("scoring_rules", [])
        }

    data = {
        "id": sub_q["sub_id"],
        "text": sub_q["text"],
        "max_score": sub_q["max_score"],
        "scoring_points": sub_q["scoring_points"],
        "score_formula": score_formula,
        "exclude_list": sub_q.get("exclude_list", []),
        "pinyin_whitelist": pinyin_whitelist
    }
    return json.dumps(data, ensure_ascii=False)


def import_scoring_points():
    """主导入函数"""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {
        "children_created": 0,
        "children_updated": 0,
        "points_created": 0,
        "points_updated": 0,
        "orphans_deleted": 0,
        "errors": 0,
    }

    try:
        # ── 1. 清理孤儿采分点（question_id 77-94） ──
        orphan_range = list(range(77, 95))
        placeholders = ','.join('?' * len(orphan_range))
        cursor.execute(
            f'DELETE FROM question_answers WHERE question_id IN ({placeholders}) AND scope_type = ?',
            orphan_range + ['scoring_point']
        )
        orphans = cursor.rowcount
        stats["orphans_deleted"] = orphans
        if orphans > 0:
            print(f"[清理] 删除 {orphans} 条孤儿采分点数据（question_id 77-94）")

        # 同时清理 question_answers 中引用不存在 question 的记录
        cursor.execute('''
            DELETE FROM question_answers
            WHERE scope_type = 'scoring_point'
            AND question_id NOT IN (SELECT id FROM questions)
        ''')
        dangling = cursor.rowcount
        if dangling > 0:
            stats["orphans_deleted"] += dangling
            print(f"[清理] 删除 {dangling} 条引用不存在题目的采分点数据")

        # ── 2. 遍历每道父题 ──
        for qdata in QUESTIONS_DATA:
            parent_id = qdata["parent_id"]
            qnum = qdata["question_number"]
            title_prefix = qdata["title_prefix"]
            pinyin_whitelist = qdata.get("pinyin_whitelist", [])

            # 验证父题是否存在
            cursor.execute('SELECT id, subject FROM questions WHERE id = ?', (parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                print(f"[跳过] 父题 id={parent_id}（{qnum} {title_prefix}）不存在于 questions 表")
                stats["errors"] += 1
                continue

            subject = parent_row["subject"]
            print(f"\n[处理] {qnum} {title_prefix}（parent_id={parent_id}, subject={subject}）")

            # ── 3. 对每个子题 ──
            for sub_q in qdata["sub_questions"]:
                sub_id = sub_q["sub_id"]
                sub_text = sub_q["text"]
                sub_max_score = sub_q["max_score"]
                sub_title = f"{title_prefix} - {sub_id}"
                rubric_json = build_sub_question_rubric(sub_q)
                # 将 pinyin_whitelist 也存入 rubric JSON
                rubric_dict = json.loads(rubric_json)
                rubric_dict["pinyin_whitelist"] = pinyin_whitelist
                rubric_json = json.dumps(rubric_dict, ensure_ascii=False)

                # 检查子题是否已存在
                existing = find_existing_child(cursor, parent_id, sub_id)

                if existing:
                    child_id = existing["id"]
                    # 更新子题
                    cursor.execute(
                        '''UPDATE questions
                           SET title = ?, content = ?, rubric = ?, max_score = ?,
                               scoring_strategy = ?, updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?''',
                        (sub_title, sub_text, rubric_json, sub_max_score,
                         sub_q["scoring_strategy"], child_id)
                    )
                    stats["children_updated"] += 1
                    print(f"  [更新] 子题 {sub_id} → id={child_id}")
                else:
                    # 创建子题
                    cursor.execute(
                        '''INSERT INTO questions
                           (subject, title, content, rubric, max_score,
                            parent_id, question_number, scoring_strategy)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (subject, sub_title, sub_text, rubric_json, sub_max_score,
                         parent_id, sub_id, sub_q["scoring_strategy"])
                    )
                    child_id = cursor.lastrowid
                    stats["children_created"] += 1
                    print(f"  [创建] 子题 {sub_id} → id={child_id}")

                # ── 4. 插入/更新采分点（每个子题一行，包含完整 JSON）──
                # 构建完整的子题采分点 JSON
                sp_full_json = build_scoring_point_json(sub_q, pinyin_whitelist)
                label = f'{sub_id}采分点'

                existing_sp = find_existing_scoring_point(cursor, child_id, sub_id)

                if existing_sp:
                    # 更新
                    cursor.execute(
                        '''UPDATE question_answers
                           SET answer_text = ?, label = ?, source = 'import'
                           WHERE id = ?''',
                        (sp_full_json, label, existing_sp["id"])
                    )
                    stats["points_updated"] += 1
                    print(f"    [更新] 采分点 {sub_id}")
                else:
                    # 插入
                    cursor.execute(
                        '''INSERT INTO question_answers
                           (question_id, scope_type, scope_id,
                            answer_text, label, source, sort_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (child_id, 'scoring_point', sub_id,
                         sp_full_json, label, 'import', 0)
                    )
                    stats["points_created"] += 1
                    print(f"    [创建] 采分点 {sub_id}")

        conn.commit()

        # ── 5. 输出统计 ──
        print(f"\n{'='*50}")
        print(f"导入完成:")
        print(f"  子题创建: {stats['children_created']}")
        print(f"  子题更新: {stats['children_updated']}")
        print(f"  采分点JSON创建: {stats['points_created']}")
        print(f"  采分点JSON更新: {stats['points_updated']}")
        print(f"  孤儿数据清理: {stats['orphans_deleted']}")
        if stats["errors"] > 0:
            print(f"  跳过/错误: {stats['errors']}")
        print(f"{'='*50}")

        # ── 6. 验证 ──
        print(f"\n[验证] 检查导入结果...")
        for qdata in QUESTIONS_DATA:
            parent_id = qdata["parent_id"]
            qnum = qdata["question_number"]
            cursor.execute(
                'SELECT id, question_number, title, max_score FROM questions WHERE parent_id = ? ORDER BY question_number',
                (parent_id,)
            )
            children = [dict(r) for r in cursor.fetchall()]
            total_sp = 0
            for child in children:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM question_answers WHERE question_id = ? AND scope_type = 'scoring_point'",
                    (child["id"],)
                )
                sp_count = cursor.fetchone()["cnt"]
                total_sp += sp_count
            print(f"  {qnum}: {len(children)} 子题, {total_sp} 采分点")

    except Exception as e:
        conn.rollback()
        print(f"\n[错误] 导入失败，已回滚: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    import_scoring_points()
