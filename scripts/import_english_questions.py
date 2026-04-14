#!/usr/bin/env python3
"""导入英语题库（12道大题 × 3道子题）到数据库"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import pdfplumber
import pandas as pd
from app.models.db_models import get_db_connection


def extract_passages(pdf_path):
    """从 PDF 提取每个主题的阅读材料"""
    passages = {}
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ''
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + '\n'

    # 找所有主题标题的起始位置
    # PDF 中有多种格式：
    #   【 0001 】Chinese New Year
    #   【\n0005\n】\nHigh-Speed Rail in China
    #   【 】\n0006 Chinese Tea Culture
    # 通用策略：找到 00XX 编号，然后向后取一行/多行作为主题名
    topic_markers = []

    # 找所有 00XX 编号位置
    for m in re.finditer(r'00(\d{2})', full_text):
        topic_num = int(m.group(1))
        if topic_num < 1 or topic_num > 12:
            continue
        pos = m.start()

        # 向后找主题名：跳过 】、空白、换行
        after = full_text[m.end():m.end() + 100]
        # 去掉前导的 】、空白、换行
        cleaned = re.sub(r'^[】\s\n]+', '', after)
        # 取第一行作为主题名
        tname = cleaned.split('\n')[0].strip()
        # 去掉可能的尾部标记
        tname = re.sub(r'\s+', ' ', tname).strip()

        if tname and len(tname) > 3 and '】' not in tname and '第' not in tname:
            topic_markers.append((topic_num, tname, pos))

    # 去重：同一个 topic_num 只保留第一个
    seen = set()
    unique_markers = []
    for tid, tname, pos in sorted(topic_markers, key=lambda x: x[2]):
        if tid not in seen:
            seen.add(tid)
            unique_markers.append((tid, tname, pos))
    topic_markers = unique_markers

    for i, (tid, tname, start) in enumerate(topic_markers):
        if tid > 12:
            continue
        # 结束位置：下一个主题或文本末尾
        if i + 1 < len(topic_markers):
            end = topic_markers[i + 1][2]
        else:
            end = len(full_text)

        chunk = full_text[start:end]

        # 找第一个 "第N题" 之前的内容作为阅读材料
        q1 = re.search(r'第\s*\d\s*题', chunk)
        if q1:
            passage = chunk[:q1.start()].strip()
        else:
            passage = chunk[:800].strip()

        # 清理：去掉开头的编号行和主题名
        # 去掉 00XX 和主题名那一段
        passage = re.sub(r'^00\d{2}\s*\n?\s*】?\s*\n?\s*' + re.escape(tname) + r'\s*', '', passage).strip()
        # 去掉残留的 【 】 行
        passage = re.sub(r'^【\s*】\s*\n?', '', passage).strip()
        passage = re.sub(r'^【\s*\d{4}\s*】\s*\n?', '', passage).strip()
        # 去掉可能的教材信息行
        passage = re.sub(r'^英语基础模块.*?【难】\s*\n?', '', passage).strip()
        passage = re.sub(r'^【高等教育出版社】.*?\n?', '', passage).strip()

        if passage and len(passage) > 20:
            passages[tid] = passage
            print(f"  主题 {tid} ({tname}): {len(passage)} 字符")

    return passages


def main():
    excel_path = 'exports/英语_评分标准.xlsx'
    pdf_path = '（英语提交）4.2普测简答题参考标准.pdf'

    print("=== 1. 读取 Excel ===")
    df = pd.read_excel(excel_path)
    print(f"共 {len(df)} 行")

    print("\n=== 2. 提取阅读材料 ===")
    passages = extract_passages(pdf_path)
    print(f"提取到 {len(passages)} 个主题的阅读材料")

    print("\n=== 3. 导入数据库 ===")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查是否已导入（幂等）
    cursor.execute("SELECT COUNT(*) FROM questions WHERE subject = 'english'")
    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"已有 {existing} 道英语题目，先清理...")
        cursor.execute("DELETE FROM question_answers WHERE question_id IN (SELECT id FROM questions WHERE subject = 'english')")
        cursor.execute("DELETE FROM test_cases WHERE question_id IN (SELECT id FROM questions WHERE subject = 'english')")
        cursor.execute("DELETE FROM rubric_script_history WHERE question_id IN (SELECT id FROM questions WHERE subject = 'english')")
        cursor.execute("DELETE FROM grading_records WHERE question_id IN (SELECT id FROM questions WHERE subject = 'english')")
        cursor.execute("DELETE FROM questions WHERE subject = 'english'")
        conn.commit()

    # 按主题分组
    topics = df.groupby('题目编号')
    parent_count = 0
    child_count = 0
    answer_count = 0

    def insert_question(subject, title, content, original_text, standard_answer,
                        rubric, max_score, question_number, difficulty, exam_name, parent_id=None):
        """用同一个 cursor 插入题目"""
        cursor.execute(
            '''INSERT INTO questions
               (subject, title, content, original_text, standard_answer,
                rubric_rules, rubric_points, rubric_script, rubric, max_score,
                question_number, difficulty, exam_name, parent_id)
               VALUES (?, ?, ?, ?, ?, '', '', '', ?, ?, ?, ?, ?, ?)''',
            (subject, title, content, original_text, standard_answer,
             rubric, max_score, question_number, difficulty, exam_name, parent_id)
        )
        return cursor.lastrowid

    def insert_answer(question_id, scope_type, scope_id, score_ratio, answer_text, label, source):
        """用同一个 cursor 插入满分答案"""
        cursor.execute(
            '''INSERT INTO question_answers
               (question_id, scope_type, scope_id, score_ratio, answer_text, label, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (question_id, scope_type, scope_id, score_ratio, answer_text, label, source)
        )

    # Excel 中可能缺失主题名（如 Topic 5），从 PDF 提取的 passages 中补充
    pdf_topic_names = {
        5: 'High-Speed Rail in China',
    }

    for topic_id, group in topics:
        topic_name = str(group.iloc[0]['主题']) if pd.notna(group.iloc[0]['主题']) else ''
        if not topic_name:
            topic_name = pdf_topic_names.get(int(topic_id), f'Topic {topic_id}')
        passage = passages.get(int(topic_id), f'(阅读材料待补充 - Topic {topic_id})')

        # 计算总分
        total_score = int(group['分值'].sum())

        # 创建父题（材料题）
        parent_id = insert_question(
            subject='english',
            title=f'English Topic {topic_id}: {topic_name}',
            content=passage,
            original_text=passage,
            standard_answer='',
            rubric='{}',
            max_score=total_score,
            question_number=str(topic_id),
            difficulty='medium',
            exam_name='4.2普测简答题',
        )
        parent_count += 1

        # 创建子题
        for _, row in group.iterrows():
            q_num = str(int(row['题号'])) if pd.notna(row['题号']) else '?'
            question_text = str(row['问题']) if pd.notna(row['问题']) else ''
            ref_answer = str(row['参考答案']) if pd.notna(row['参考答案']) else ''
            max_score = int(row['分值']) if pd.notna(row['分值']) else 2

            child_id = insert_question(
                subject='english',
                title=f'Q{topic_id}.{q_num}: {question_text[:30]}',
                content=question_text,
                original_text=question_text,
                standard_answer=ref_answer,
                rubric='{}',
                max_score=max_score,
                question_number=f'{topic_id}.{q_num}',
                difficulty='medium',
                exam_name='4.2普测简答题',
                parent_id=parent_id,
            )
            child_count += 1

            # 添加标准答案到 question_answers
            if ref_answer and ref_answer != 'nan':
                insert_answer(
                    question_id=child_id,
                    scope_type='question',
                    scope_id='',
                    score_ratio=1.0,
                    answer_text=ref_answer,
                    label='标准答案',
                    source='migrated',
                )
                answer_count += 1

            # 添加采分点到 question_answers
            scoring_points = str(row['采分点']) if pd.notna(row['采分点']) else ''
            if scoring_points and scoring_points != 'nan':
                # 解析 (A) xxx (B) xxx 格式
                sp_items = re.split(r'\(([A-Z])\)', scoring_points)
                sp_idx = 0
                for k in range(1, len(sp_items) - 1, 2):
                    letter = sp_items[k]
                    desc = sp_items[k + 1].strip().rstrip('。').rstrip('.')
                    if desc:
                        sp_idx += 1
                        insert_answer(
                            question_id=child_id,
                            scope_type='scoring_point',
                            scope_id=str(sp_idx),
                            score_ratio=1.0,
                            answer_text=desc,
                            label=f'采分点{letter}',
                            source='migrated',
                        )
                        answer_count += 1

        conn.commit()

    conn.close()
    print(f"\n导入完成:")
    print(f"  父题: {parent_count}")
    print(f"  子题: {child_count}")
    print(f"  满分答案/采分点: {answer_count}")


if __name__ == '__main__':
    main()
