"""
英语简答题 Word 文档解析器
支持两种格式：
  1. 拆分后的单题文件（只有第一步逐项判定）
  2. 原始完整文档（含12道题 + 通用评分规则）
"""
import re
import subprocess
import tempfile
import os
from typing import List, Dict, Optional
from io import BytesIO

from docx import Document


# ===== 英语通用评分规则（第二步+第三步，12题共用） =====
ENGLISH_COMMON_RUBRIC = """第二步：计分规则
1.答案必须基于材料：脱离材料的主观回答一律 0 分。
2.采分点（关键词）制：每个问题的满分答案由 1-2 个必有关键词构成。
写出全部关键词且语义正确得2分或者写出部分关键词得1分或者未写出任何关键词,拼音或汉字不得分
3.语言宽容度：
时态、语态、单复数等语法错误不扣分（只要不影响关键词识别）。
关键词拼写错误：若与正确形式明显不符，扣 1分。
大小写、标点符号、冠词错误不扣分。
拼音或汉字不给分
4.冗余信息处理：
额外正确信息 → 不扣分。
错误信息（与材料矛盾）→ 扣 1分。
第三步：输出格式
简要说明每个要素的判断结果和评价。"""


# ===== 正则模板 =====
MODULE_TITLE = re.compile(r'^英语基础模块\s*M\d+\s+U\d+【高等教育出版社】【教材发展研究所】【语篇知识/文化素养】【难】$')
QUESTION_ID = re.compile(r'^【(\d{4})】\s*(.*)$')
QUESTIONS_HEADER = re.compile(r'^简答题问题（答案均出自原文）$')
SCORING_INSTRUCTION = re.compile(r'^请严格按照以下规则对学生答案进行评分：')
STEP1 = re.compile(r'^第一步：逐项判定')

# ===== 英语通用评分规则 HTML 版（用于 original_text 拼接） =====
ENGLISH_COMMON_RUBRIC_HTML = """<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>第二步：计分规则</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>1.</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>答案必须基于材料：脱离材料的主观回答一律 0 分。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>2.</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>采分点（关键词）制：每个问题的满分答案由 1-2 个必有关键词构成。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>写出全部关键词且语义正确</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>得</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>2分</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>或者</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>写出部分关键词</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>得</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>1分</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>或者</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>未写出任何关键词,</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>拼音或汉字不得</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>分</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>3.</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>语言宽容度：</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>时态、语态、单复数等语法错误不扣分（只要不影响关键词识别）。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>关键词拼写错误：若与正确形式明显不符，扣 </strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>1</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>分。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>大小写、</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>标点符号、</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>冠词错误不扣分。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>拼音或汉字不给分</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>4.</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>冗余信息处理：</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>额外正确信息 → 不扣分。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>错误信息（与材料矛盾）→ 扣 </strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>1</strong></span><span style="font-size:12.0pt;font-family:Times New Roman"><strong>分。</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>第三步：输出格式</strong></span></p>
<p><span style="font-size:12.0pt;font-family:Times New Roman"><strong>简要说明每个要素的判断结果和评价。</strong></span></p>"""
STEP2 = re.compile(r'^第二步：计分规则')
SUB_QUESTION = re.compile(r'^第[123]题')
REFERENCE_ANSWER = re.compile(r'^参考答案：(.+)$')
# 子题问题行（带编号或不带）
SUB_Q_LINE = re.compile(r'^(\d+)\.\s*(.+)')


def _extract_plain_text(paragraphs: list) -> List[str]:
    """提取段落纯文本列表"""
    return [p.text for p in paragraphs]


def _docx_to_html_by_paragraphs(paragraphs: list) -> Dict[int, str]:
    """把每个段落转为 HTML（保留格式），返回 {段落索引: html}"""
    result = {}
    for i, para in enumerate(paragraphs):
        parts = []
        for run in para.runs:
            text = run.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if not text:
                continue
            styles = []
            if run.font.size:
                styles.append(f'font-size:{run.font.size.pt}pt')
            if run.font.color and run.font.color.rgb:
                hex_color = str(run.font.color.rgb)
                styles.append(f'color:#{hex_color}')
            if run.font.name:
                styles.append(f'font-family:{run.font.name}')

            if run.bold:
                text = f'<strong>{text}</strong>'
            if run.italic:
                text = f'<em>{text}</em>'
            if run.underline:
                text = f'<u>{text}</u>'
            if styles:
                text = f'<span style="{";".join(styles)}">{text}</span>'
            parts.append(text)

        align_map = {1: 'center', 2: 'right', 3: 'justify'}
        align = align_map.get(para.alignment, '')
        align_attr = f' style="text-align:{align}"' if align else ''

        content = ''.join(parts) if parts else para.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        result[i] = f'<p{align_attr}>{content}</p>'
    return result


def _find_markers(paragraphs: list) -> List[Dict]:
    """扫描所有段落，找到题目标记和关键分隔符"""
    markers = []
    for i, para in enumerate(paragraphs):
        text = para.text.strip()
        m = QUESTION_ID.match(text)
        if m:
            markers.append({
                'type': 'question_id',
                'index': i,
                'number': m.group(1),
                'title': m.group(2).strip(),
            })
    return markers


def _extract_answers_from_rubric(rubric_text: str) -> str:
    """从评分细则中提取所有参考答案"""
    answers = []
    for line in rubric_text.split('\n'):
        m = REFERENCE_ANSWER.match(line.strip())
        if m:
            answers.append(m.group(1).strip())
    return '\n'.join(answers)


def _parse_single_question(all_texts: list, start: int, end: int,
                           html_map: Dict[int, str],
                           module_title: str = '') -> Dict:
    """解析单道题（从模块标题到评分细则结束）"""
    texts = all_texts[start:end]

    # 找关键分隔位置（相对索引）
    q_header_rel = None  # "简答题问题"
    scoring_rel = None   # "请严格按照"
    step1_rel = None     # "第一步"

    for rel_i, text in enumerate(texts):
        t = text.strip()
        if q_header_rel is None and QUESTIONS_HEADER.match(t):
            q_header_rel = rel_i
        if scoring_rel is None and SCORING_INSTRUCTION.match(t):
            scoring_rel = rel_i
        if step1_rel is None and STEP1.match(t):
            step1_rel = rel_i

    # 提取题号和标题：扫描前几行找到【000x】标记
    question_number = ''
    title = ''
    id_rel = None  # 题号行的相对索引
    for rel_i in range(min(5, len(texts))):
        m_id = QUESTION_ID.match(texts[rel_i].strip())
        if m_id:
            question_number = m_id.group(1)
            title = m_id.group(2).strip()
            id_rel = rel_i
            break

    # 如果编号行没有标题，下一行可能是标题
    if id_rel is not None and not title and (id_rel + 1) < len(texts):
        next_line = texts[id_rel + 1].strip()
        # 确认下一行不是阅读材料的子标题或问题
        if next_line and not QUESTIONS_HEADER.match(next_line) and not SUB_Q_LINE.match(next_line):
            title = next_line

    # content = 阅读材料 + 问题+答案（从题号行之后 到 "请严格按照"之前）
    content_start = (id_rel + 1) if id_rel is not None else 0
    # 如果有标题行且标题在编号下一行，跳过标题行
    if id_rel is not None and title and (id_rel + 1) < len(texts) and texts[id_rel + 1].strip() == title:
        content_start = id_rel + 2

    if q_header_rel is not None:
        # 阅读材料部分
        passage_texts = texts[content_start:q_header_rel]
        # 问题+答案部分
        if scoring_rel is not None:
            qa_texts = texts[q_header_rel:scoring_rel]
        else:
            qa_texts = texts[q_header_rel:]
        content = '\n'.join(t.strip() for t in passage_texts + qa_texts if t.strip())
    else:
        # 单题文件可能没有"简答题问题"头，取所有非评分部分
        if scoring_rel is not None:
            content = '\n'.join(t.strip() for t in texts[content_start:scoring_rel] if t.strip())
        elif step1_rel is not None:
            content = '\n'.join(t.strip() for t in texts[content_start:step1_rel] if t.strip())
        else:
            content = '\n'.join(t.strip() for t in texts[content_start:] if t.strip())

    # content_html = 对应段落的 HTML
    html_parts = []
    if q_header_rel is not None:
        html_range = list(range(start + 2, start + (scoring_rel if scoring_rel else len(texts))))
    elif step1_rel is not None:
        html_range = list(range(start, start + step1_rel))
    elif scoring_rel is not None:
        html_range = list(range(start, start + scoring_rel))
    else:
        html_range = list(range(start, end))

    for idx in html_range:
        if idx in html_map:
            html_parts.append(html_map[idx])
    content_html = '\n'.join(html_parts)

    # rubric_script = 评分细则（从"第一步"或"请严格按照"到结尾）
    rubric_start_rel = step1_rel if step1_rel is not None else scoring_rel
    if rubric_start_rel is not None:
        rubric_texts = texts[rubric_start_rel:]
        rubric_script = '\n'.join(t.strip() for t in rubric_texts if t.strip())
    else:
        rubric_script = ''

    # 拼接英语通用评分规则（第二步+第三步）
    if rubric_script and '第二步' not in rubric_script:
        rubric_script = rubric_script + '\n' + ENGLISH_COMMON_RUBRIC

    # 标准答案：从 rubric_script 中提取
    standard_answer = _extract_answers_from_rubric(rubric_script) if rubric_script else ''

    # 满分值：默认 6（3题 × 2分）
    max_score = 6

    # exam_name：从模块标题提取
    exam_name = module_title.strip() if module_title else ''

    # difficulty：从模块标题末尾的【难/中/易】提取
    difficulty = 'medium'
    if exam_name:
        m_diff = re.search(r'【(难|中|易)】\s*$', exam_name)
        if m_diff:
            difficulty = {'难': 'hard', '中': 'medium', '易': 'easy'}[m_diff.group(1)]

    # original_text = 该题范围内全部段落的 HTML（含评分细则，保留格式）
    original_html_parts = []
    for idx in range(start, end):
        if idx in html_map:
            original_html_parts.append(html_map[idx])
    original_text = '\n'.join(original_html_parts)

    # 拼接通用评分规则 HTML 到 original_text
    if '第二步' not in original_text:
        original_text = original_text + '\n' + ENGLISH_COMMON_RUBRIC_HTML

    return {
        'question_number': question_number,
        'title': title,
        'content': content,
        'content_html': content_html,
        'original_text': original_text,
        'standard_answer': standard_answer,
        'rubric_script': rubric_script,
        'rubric_points': '',
        'max_score': max_score,
        'difficulty': difficulty,
        'subject': 'english',
        'exam_name': exam_name,
    }


def parse_english_docx(file_stream) -> List[Dict]:
    """
    解析英语简答题 Word 文档。
    支持单题文件和完整文档（含多题）。
    返回题目列表。
    """
    doc = Document(file_stream)
    paragraphs = doc.paragraphs
    total = len(paragraphs)

    if total == 0:
        return []

    texts = _extract_plain_text(paragraphs)
    html_map = _docx_to_html_by_paragraphs(paragraphs)

    # 找到所有【000x】标记
    markers = _find_markers(paragraphs)

    if not markers:
        return []

    # 找模块标题（在每个标记前一行）
    module_titles = {}
    for mk in markers:
        idx = mk['index']
        if idx > 0 and MODULE_TITLE.match(texts[idx - 1].strip()):
            module_titles[idx] = texts[idx - 1].strip()

    # 找到所有"第二步：计分规则"位置（用于切割完整文档）
    step2_positions = []
    for i, text in enumerate(texts):
        if STEP2.match(text.strip()):
            step2_positions.append(i)

    # 构建每题的切割范围
    questions = []
    for mi, mk in enumerate(markers):
        start = mk['index'] - 1  # 包含模块标题
        if start < 0:
            start = 0
        # 如果前一行不是模块标题，从标记行开始
        if start not in module_titles and mk['index'] > 0:
            if texts[start].strip() in module_titles.get(mk['index'], ''):
                pass  # 模块标题行
            else:
                start = mk['index']

        # 截止点：下一个标记之前，或者下一个"第二步"之前
        end = total
        # 先看有没有后面的标记
        if mi + 1 < len(markers):
            end = markers[mi + 1]['index'] - 1  # 到下一个标记的模块标题之前
        # 再看有没有"第二步"在当前标记和下一个标记之间
        for sp in step2_positions:
            if sp > mk['index'] and sp < end:
                end = sp
                break

        module_title = module_titles.get(mk['index'], '')
        q = _parse_single_question(texts, start, end, html_map, module_title)
        questions.append(q)

    return questions


def parse_english_docx_from_bytes(data: bytes) -> List[Dict]:
    """从字节数据解析 Word 文档"""
    return parse_english_docx(BytesIO(data))
