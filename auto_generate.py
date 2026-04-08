"""
AI 自动出题 + 评分脚本 + 测试用例生成器

用法：
    python auto_generate.py --subject politics --count 20 --testcases 7
    python auto_generate.py --subject chinese --count 20
    python auto_generate.py --subject english --count 20
    python auto_generate.py --all  # 三科各 20 题

支持断点续跑：已存在的题目会跳过，只补充缺失的。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
from loguru import logger

from config.settings import GRADING_CONFIG
from app.models.db_models import (
    add_question, get_questions, get_test_cases,
    add_test_case, get_syllabus, get_db_connection
)

# =============================================================================
# 科目配置
# =============================================================================

SUBJECTS = {
    'politics': {
        'label': '思想政治',
        'grade': '湖南省中等职业学校2年级',
        'topics': [
            '中国特色社会主义',
            '经济与社会',
            '政治与法治',
            '哲学与人生',
            '职业道德与法治',
            '心理健康与职业生涯'
        ],
        'difficulty_range': (4, 8),  # 分值范围
    },
    'chinese': {
        'label': '语文',
        'grade': '湖南省中等职业学校2年级',
        'topics': [
            '现代文阅读理解',
            '古诗词鉴赏',
            '文言文翻译与理解',
            '语言表达与应用',
            '写作基础知识',
            '中国传统文化常识'
        ],
        'difficulty_range': (6, 15),
    },
    'english': {
        'label': '英语',
        'grade': '湖南省中等职业学校2年级',
        'topics': [
            '阅读理解',
            '语法与词汇',
            '翻译（中译英/英译中）',
            '情景交际',
            '书面表达基础',
            '时态与语态'
        ],
        'difficulty_range': (5, 12),
    },
}

# =============================================================================
# LLM 调用
# =============================================================================

def get_client():
    """获取 OpenAI 兼容客户端"""
    import os
    api_key = GRADING_CONFIG.get('api_key') or os.environ.get('QWEN_API_KEY', '')
    base_url = GRADING_CONFIG.get('base_url') or os.environ.get('QWEN_BASE_URL', '')
    if not api_key:
        # 直接从 .env 读取
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('QWEN_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('QWEN_BASE_URL='):
                    base_url = line.split('=', 1)[1].strip()

    return OpenAI(api_key=api_key, base_url=base_url or None)


def call_llm(client, model, system_prompt, user_prompt, temperature=0.3, max_tokens=4096):
    """调用 LLM，返回文本"""
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM 调用失败 (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    return None


def extract_json(text):
    """从文本中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# =============================================================================
# Prompt 模板
# =============================================================================

QUESTION_GEN_SYSTEM = """你是一位资深职业教育命题专家，专门为中等职业学校学生出题。

要求：
1. 题目必须是简答题或论述题（不要出选择题、填空题、判断题）
2. 题目要符合中职学生的知识水平，不要太难也不要太简单
3. 每道题必须有明确的标准答案，不能是开放性讨论题
4. 评分要点必须清晰、可量化

输出格式（严格 JSON）：
{
    "title": "简短题目标题（15字以内）",
    "content": "完整的题目内容",
    "max_score": 分值（整数）,
    "difficulty": "easy/medium/hard",
    "knowledge": "本题考查的知识点",
    "content_type": "简答题",
    "standard_answer": "完整的标准答案，包含所有得分要点",
    "rubric_rules": "整体评分规则说明",
    "rubric_points": "每行一个得分点，格式：要点描述 (X分)"
}

注意：
- rubric_points 中各要点分值之和必须等于 max_score
- 标准答案要完整、准确，适合做评分参照
- 不要输出任何 JSON 以外的内容"""


QUESTION_GEN_USER = """请为【{subject_label}】科目出一道关于【{topic}】的简答题。

要求：
- 适用对象：{grade}
- 分值：{score} 分
- 难度：{difficulty}
- 知识领域：{topic}

{existing_hint}

请直接输出 JSON，不要任何解释。"""


RUBRIC_SCRIPT_SYSTEM = """你是一位资深教育测评专家，擅长将评分规则转化为结构化的、无歧义的评分指令。

你的任务：根据提供的题目信息，生成一段【结构化评分脚本】。这段脚本将被保存并作为大模型自动阅卷时的**唯一评分依据**。

要求：
1. **完全自包含**：无需任何额外上下文就能准确评分
2. **跨系统一致**：不同大模型拿到同一脚本+同一答案，应给出相同分数
3. **容错性强**：能正确处理各种考生作答情况

结构要求：
- 【题目信息】：完整复述题目内容和满分值
- 【标准答案要点】：核心要点 + 核心含义 + 关键词 + 等价表述
- 【逐项评分规则】：每个得分点的得分条件、部分得分、不得分条件、易混淆判断
- 【作答情况分类】：完整/部分/空白/关键但简短等
- 【扣分规则】：明确的扣分条件
- 【总分计算】：总分 = 各项得分 - 扣分，范围 [0, 满分]
- 【输出格式要求】：{"总分": X, "评语": "..."}

语言要求：
- 禁止："酌情给分"、"视情况"、"适当给分"
- 必须："如果...则得X分"、"只要提到...即得X分"、"未提到...则0分"

直接输出评分脚本内容，不要加任何解释。"""


TESTCASE_GEN_SYSTEM = """你是一位经验丰富的阅卷老师，熟悉各类考生作答模式。

你的任务：根据题目和标准答案，生成多份模拟考生作答，覆盖不同的得分水平。

每份作答必须：
1. 真实可信——像真实考生写的，不能太完美也不能太假
2. 分数明确——根据评分规则可以明确给分
3. 覆盖典型情况——满分、部分对、全错、偏题、口语化等

输出格式（严格 JSON 数组）：
[
    {
        "description": "简短描述（如：满分作答、要点不全、完全偏题）",
        "case_type": "simulated",
        "answer_text": "模拟的考生作答内容",
        "expected_score": 期望分数
    }
]

注意：
- expected_score 必须是具体数字，不能是范围
- 不同用例的分数应形成梯度分布
- 不要输出任何 JSON 以外的内容"""


TESTCASE_GEN_USER = """请为以下题目生成 {count} 份模拟考生作答：

【题目】
{content}

【满分】
{max_score} 分

【标准答案】
{standard_answer}

【评分要点】
{rubric_points}

请生成 {count} 份不同水平的作答，覆盖以下梯度（按实际满分调整）：
1. 满分或接近满分
2. 较好（约 70-80%）
3. 中等（约 50-60%）
4. 偏低（约 30-40%）
5. 较差（约 10-20%）
6. 几乎全错或偏题（约 0-10%）
7. 空白或无相关内容（0分）

直接输出 JSON 数组，不要任何解释。"""


# =============================================================================
# 核心逻辑
# =============================================================================

def generate_question(client, model, subject_key, topic, existing_titles):
    """生成一道题"""
    cfg = SUBJECTS[subject_key]
    import random
    score = random.randint(cfg['difficulty_range'][0], cfg['difficulty_range'][1])
    difficulty = random.choice(['easy', 'medium', 'medium', 'hard'])

    # 避免重复
    hint = ""
    if existing_titles:
        sample = existing_titles[:5]
        hint = f"已有的题目标题（请不要重复）：{', '.join(sample)}"

    user_prompt = QUESTION_GEN_USER.format(
        subject_label=cfg['label'],
        topic=topic,
        grade=cfg['grade'],
        score=score,
        difficulty={'easy': '简单', 'medium': '中等', 'hard': '困难'}[difficulty],
        existing_hint=hint
    )

    raw = call_llm(client, model, QUESTION_GEN_SYSTEM, user_prompt, temperature=0.7, max_tokens=2048)
    if not raw:
        logger.error("题目生成失败：LLM 无响应")
        return None

    data = extract_json(raw)
    if not data or not data.get('content'):
        logger.error(f"题目生成失败：无法解析 JSON，原始响应前200字: {raw[:200]}")
        return None

    # 补充默认值
    data.setdefault('max_score', score)
    data.setdefault('difficulty', difficulty)
    data.setdefault('knowledge', topic)
    data.setdefault('content_type', '简答题')
    return data


def generate_rubric_script(client, model, question_data):
    """为一道题生成评分脚本"""
    user_prompt = f"""请根据以下信息生成结构化评分脚本：

【题目内容】
{question_data['content']}

【满分】
{question_data['max_score']} 分

【标准答案】
{question_data['standard_answer']}

【评分规则】
{question_data.get('rubric_rules', '无')}

【分数分布/得分要点】
{question_data.get('rubric_points', '无')}"""

    raw = call_llm(client, model, RUBRIC_SCRIPT_SYSTEM, user_prompt, temperature=0.0, max_tokens=4096)
    if not raw or len(raw) < 50:
        logger.warning("评分脚本生成失败或内容过短")
        return None
    return raw


def generate_test_cases(client, model, question_data, count):
    """为一道题生成测试用例"""
    user_prompt = TESTCASE_GEN_USER.format(
        count=count,
        content=question_data['content'],
        max_score=question_data['max_score'],
        standard_answer=question_data['standard_answer'],
        rubric_points=question_data.get('rubric_points', '无')
    )

    raw = call_llm(client, model, TESTCASE_GEN_SYSTEM, user_prompt, temperature=0.6, max_tokens=4096)
    if not raw:
        logger.error("测试用例生成失败：LLM 无响应")
        return []

    # 尝试解析 JSON 数组
    cases = None
    try:
        cases = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\[[\s\S]*\]', raw)
        if match:
            try:
                cases = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not cases or not isinstance(cases, list):
        logger.error(f"测试用例解析失败，原始响应前200字: {raw[:200]}")
        return []

    # 校验和修正
    valid_cases = []
    for c in cases:
        if not c.get('answer_text') or c.get('expected_score') is None:
            continue
        valid_cases.append({
            'description': c.get('description', '模拟作答'),
            'case_type': c.get('case_type', 'simulated'),
            'answer_text': c['answer_text'],
            'expected_score': float(c['expected_score']),
        })
    return valid_cases


def get_existing_titles(subject_key):
    """获取已有题目的标题，用于去重"""
    questions = get_questions(subject_key)
    return [q.get('title', '') for q in questions if q.get('title')]


def count_existing(subject_key):
    """统计已有题目数"""
    questions = get_questions(subject_key)
    return len(questions)


def run_generation(subject_key, count, testcase_count, model=None):
    """生成指定科目的题目"""
    if subject_key not in SUBJECTS:
        logger.error(f"不支持的科目: {subject_key}")
        return

    cfg = SUBJECTS[subject_key]
    client = get_client()

    if not model:
        # 从配置获取模型名
        import os
        model = os.environ.get('QWEN_MODEL', '')
        if not model:
            env_path = Path(__file__).parent / '.env'
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith('QWEN_MODEL='):
                        model = line.split('=', 1)[1].strip()
        if not model:
            model = 'qwen-max'

    existing_count = count_existing(subject_key)
    logger.info(f"科目 [{cfg['label']}] 现有 {existing_count} 题，目标生成 {count} 题")

    topics = cfg['topics']
    generated = 0

    for i in range(count):
        topic = topics[i % len(topics)]
        existing_titles = get_existing_titles(subject_key)

        logger.info(f"[{cfg['label']}] 生成第 {i+1}/{count} 题，主题：{topic}")

        # 1. 生成题目
        question_data = generate_question(client, model, subject_key, topic, existing_titles)
        if not question_data:
            logger.warning(f"第 {i+1} 题生成失败，跳过")
            continue

        title = question_data.get('title', question_data['content'][:30])
        logger.info(f"  题目: {title}")

        # 2. 生成评分脚本
        logger.info(f"  生成评分脚本...")
        rubric_script = generate_rubric_script(client, model, question_data)
        if rubric_script:
            logger.info(f"  评分脚本已生成 ({len(rubric_script)} 字)")
        else:
            logger.warning(f"  评分脚本生成失败，继续保存题目")

        # 3. 保存题目到数据库
        rubric_json = json.dumps({
            'rubricRules': question_data.get('rubric_rules', ''),
            'points': [{'description': p.strip()} for p in question_data.get('rubric_points', '').split('\n') if p.strip()],
            'rubricScript': rubric_script or '',
            'knowledge': question_data.get('knowledge', topic),
            'contentType': question_data.get('content_type', '简答题'),
            'standardAnswer': question_data.get('standard_answer', ''),
        }, ensure_ascii=False)

        question_id = add_question(
            subject=subject_key,
            title=title,
            content=question_data['content'],
            original_text=question_data['content'],
            standard_answer=question_data.get('standard_answer', ''),
            rubric_rules=question_data.get('rubric_rules', ''),
            rubric_points=question_data.get('rubric_points', ''),
            rubric_script=rubric_script or '',
            rubric=rubric_json,
            max_score=float(question_data.get('max_score', 10)),
            quality_score=None
        )
        logger.info(f"  题目已保存 (ID: {question_id})")

        # 4. 生成测试用例
        logger.info(f"  生成 {testcase_count} 个测试用例...")
        cases = generate_test_cases(client, model, question_data, testcase_count)
        saved_cases = 0
        for case in cases:
            try:
                add_test_case(
                    question_id=question_id,
                    answer_text=case['answer_text'],
                    expected_score=case['expected_score'],
                    description=case['description'],
                    case_type=case['case_type']
                )
                saved_cases += 1
            except Exception as e:
                logger.warning(f"  保存测试用例失败: {e}")

        logger.info(f"  已保存 {saved_cases}/{len(cases)} 个测试用例")
        generated += 1

        # 短暂间隔，避免速率限制
        if i < count - 1:
            time.sleep(1)

    logger.info(f"\n{'='*50}")
    logger.info(f"科目 [{cfg['label']}] 完成：生成 {generated}/{count} 题")
    logger.info(f"{'='*50}\n")
    return generated


def main():
    parser = argparse.ArgumentParser(description='AI 自动出题 + 评分脚本 + 测试用例生成器')
    parser.add_argument('--subject', type=str, choices=['politics', 'chinese', 'english'],
                        help='科目: politics/chinese/english')
    parser.add_argument('--all', action='store_true', help='生成所有科目')
    parser.add_argument('--count', type=int, default=20, help='每科生成题目数 (默认 20)')
    parser.add_argument('--testcases', type=int, default=7, help='每题生成测试用例数 (默认 7)')
    parser.add_argument('--model', type=str, default=None, help='指定模型名称')

    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('请指定 --subject 或 --all')

    subjects = ['politics', 'chinese', 'english'] if args.all else [args.subject]

    logger.info(f"开始自动生成题目")
    logger.info(f"科目: {', '.join(SUBJECTS[s]['label'] for s in subjects)}")
    logger.info(f"每科: {args.count} 题, 每题: {args.testcases} 测试用例")
    logger.info(f"预估 LLM 调用: {len(subjects) * args.count * 3} 次")
    logger.info(f"{'='*50}")

    total = 0
    for subj in subjects:
        n = run_generation(subj, args.count, args.testcases, args.model)
        total += (n or 0)

    logger.info(f"\n全部完成！共生成 {total} 道题目")


if __name__ == '__main__':
    main()
