#!/usr/bin/env python3
"""将英语参考标准PDF转换为Excel格式（逐题逐采分点）"""

import re
import pdfplumber
import pandas as pd
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def find_topic_at(text, pos):
    """找到位置 pos 所属的主题编号"""
    # 往前搜最近的 000x 编号
    chunk = text[max(0, pos - 3000):pos]
    matches = re.findall(r'00(0\d|1[0-2])', chunk)
    if matches:
        return '00' + matches[-1]
    return '0000'


def find_topic_titles(text):
    """找到所有主题标题"""
    titles = {}
    for m in re.finditer(r'【\s*(\d{4})\s*】(.+?)(?:\n|$)', text):
        titles[m.group(1)] = m.group(2).strip()
    for m in re.finditer(r'【\s*】\s*\n(\d{4})\s+(.+?)(?:\n|$)', text):
        num = m.group(1)
        if num not in titles:
            titles[num] = m.group(2).strip()
    return titles


def parse_all_questions(text):
    """全局搜 第N题，逐题解析"""
    topic_titles = find_topic_titles(text)
    rows = []

    # 找到所有 "第N题" 的位置（兼容 "第1题" "第 1题" "第1 题" 等格式）
    q_positions = []
    for m in re.finditer(r'第\s*(\d)\s*题', text):
        q_positions.append((int(m.group(1)), m.start(), m.end()))

    # 合并相邻的标题和内容行（"第1题\n问题："这种跨行情况）
    for i, (q_num, line_start, content_start) in enumerate(q_positions):
        # 找到下一题的开始位置
        if i + 1 < len(q_positions):
            block_end = q_positions[i + 1][1]
        else:
            block_end = min(content_start + 2000, len(text))

        block = text[content_start:block_end]

        # 找到所属主题
        qid = find_topic_at(text, line_start)
        topic_name = topic_titles.get(qid, '')

        # 提取问题
        question_text = ''
        q_match = re.search(r'问题：(.+?)(?:\n|$)', block)
        if q_match:
            question_text = q_match.group(1).strip()

        # 提取参考答案
        ref_answer = ''
        ra_match = re.search(r'参考答案：(.+?)(?:\n|$)', block)
        if ra_match:
            ref_answer = ra_match.group(1).strip()

        # 提取采分点
        scoring_points = []
        # 匹配 采分点（关键词）： 后面的内容，直到 得分 表
        sp_match = re.search(r'采分点[（(]关键词[)）]：?\s*(.*?)(?=\n得分|\n示例|\n同义|\n注意|$)', block, re.DOTALL)
        if sp_match:
            sp_text = sp_match.group(1).strip()
            # 按 (A) (B) 分割
            sp_items = re.split(r'\(([A-Z])\)', sp_text)
            for k in range(1, len(sp_items) - 1, 2):
                letter = sp_items[k]
                desc = sp_items[k + 1].strip().rstrip('。').rstrip('.')
                scoring_points.append(f"({letter}) {desc}")
        else:
            # 简单格式：采分点：keyword
            sp_match2 = re.search(r'采分点[：:]\s*(.+?)(?:\n得分|\n示例|\n同义|$)', block)
            if sp_match2:
                scoring_points.append(sp_match2.group(1).strip())

        # 提取同义表达可接受范围
        acceptable = []
        acc_match = re.search(r'同义表达可接受范围：?\s*(.*?)(?=\n示例|\n注意|\n第\d题|$)', block, re.DOTALL)
        if acc_match:
            acc_text = acc_match.group(1).strip()
            for line in acc_text.split('\n'):
                line = line.strip()
                if line and '→' in line:
                    acceptable.append(line)
                elif line and len(line) > 3 and not line.startswith('示例'):
                    acceptable.append(line)

        # 提取不接受 / 易混淆
        unacceptable = []
        unacc_match = re.search(r'(?:不接受|易混淆)[：:]?\s*(.*?)(?=\n示例|\n同义|\n注意|\n第\d题|$)', block, re.DOTALL)
        if unacc_match:
            for line in unacc_match.group(1).split('\n'):
                line = line.strip().lstrip('- ')
                if line and len(line) > 2:
                    unacceptable.append(line)

        # 提取示例
        examples = []
        ex_match = re.search(r'示例[：:]\s*(.*?)(?=\n注意|\n同义|\n第\d题|\n第二步|\n各题评分|$)', block, re.DOTALL)
        if ex_match:
            for line in ex_match.group(1).split('\n'):
                line = line.strip().lstrip('- ')
                if line and '→' in line:
                    examples.append(line)

        rows.append({
            '题目编号': qid,
            '主题': topic_name[:50],
            '题号': q_num,
            '问题': question_text,
            '参考答案': ref_answer,
            '采分点': '\n'.join(scoring_points) if scoring_points else '',
            '同义可接受': '\n'.join(acceptable) if acceptable else '',
            '不接受/易混淆': '\n'.join(unacceptable) if unacceptable else '',
            '示例': '\n'.join(examples) if examples else '',
            '分值': 2,
        })

    return rows


def main():
    pdf_path = Path('（英语提交）4.2普测简答题参考标准.pdf')
    if not pdf_path.exists():
        print(f"文件不存在: {pdf_path}")
        return

    print(f"读取PDF: {pdf_path}")
    text = extract_text_from_pdf(str(pdf_path))
    print(f"提取到 {len(text)} 字符")

    all_rows = parse_all_questions(text)
    print(f"共解析 {len(all_rows)} 道题")

    # 按主题统计
    from collections import Counter
    topic_counts = Counter(r['题目编号'] for r in all_rows)
    for qid in sorted(topic_counts):
        print(f"  {qid}: {topic_counts[qid]} 道题")

    if not all_rows:
        print("未解析到任何题目")
        return

    # 保存为Excel
    output_path = Path('exports/英语_评分标准.xlsx')
    output_path.parent.mkdir(exist_ok=True)

    df = pd.DataFrame(all_rows)
    with pd.ExcelWriter(str(output_path), engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='评分标准', index=False)

        ws = writer.sheets['评分标准']
        col_widths = {
            'A': 12, 'B': 40, 'C': 6, 'D': 50,
            'E': 50, 'F': 45, 'G': 45, 'H': 35, 'I': 40, 'J': 8
        }
        for col_letter, width in col_widths.items():
            ws.column_dimensions[col_letter].width = width

    print(f"Excel已保存: {output_path}")


if __name__ == '__main__':
    main()
