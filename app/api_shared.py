"""
api_routes 共享对象 — Blueprint、评分引擎、公共辅助函数、共享 Prompt 常量
所有 routes_xxx.py 从这里 import，避免循环依赖
"""
import json
import re
import time
from flask import Blueprint, request, jsonify, session
from loguru import logger
from app.models.db_models import (
    add_question, get_questions, get_question,
    update_question, delete_question,
    add_grading_record, get_grading_history,
    create_batch_task, update_batch_task, get_batch_task,
    get_syllabus, get_all_syllabus, upsert_syllabus, delete_syllabus,
    add_test_case, get_test_cases, get_test_case,
    update_test_case, delete_test_case, update_test_case_result,
    get_all_test_cases_overview, get_all_test_cases_with_question,
    save_script_version, get_script_history, get_script_version,
    check_sensitive_words,
    get_previous_grade,
    update_script_version_result,
    get_sensitive_words, add_sensitive_word, update_sensitive_word,
    delete_sensitive_word, batch_add_sensitive_words,
    get_users, get_user, add_user as db_add_user, update_user, delete_user,
    log_bug,
    get_question_answers, add_question_answer, update_question_answer, delete_question_answer,
    get_grading_param, get_all_grading_params, set_grading_param,
    get_child_questions, get_question_with_children,
)
from app.qwen_engine import QwenGradingEngine
from app.models.registry import model_registry
from config.settings import GRADING_CONFIG

api_bp = Blueprint('api', __name__, url_prefix='/api')
grading_engine = QwenGradingEngine(GRADING_CONFIG)


def _check_subject_access(target_subject):
    """检查当前 session 用户是否有权访问目标科目。admin 不受限。"""
    if session.get('role') == 'admin':
        return True
    return session.get('subject') == target_subject


def _session_subject():
    """返回当前 session 的科目，admin 返回 None（表示全部）"""
    if session.get('role') == 'admin':
        return None
    return session.get('subject')


PROVIDER_NAMES = {
    'qwen': '通义千问',
    'glm': '智谱 GLM',
    'ernie': '文心一言',
    'doubao': '豆包',
    'xiaomi_mimimo': '小米 Mimimo',
    'minimax': 'MiniMax',
    'spark': '讯飞星火',
}


def _call_llm_sync(system_prompt: str, user_prompt: str) -> str:
    """同步调用 LLM，返回原始文本"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = grading_engine.client.chat.completions.create(
                model=grading_engine.model,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
                stream=False,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM调用失败(第{attempt+1}次): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return ''


def _parse_json_from_llm(raw: str) -> dict:
    """从 LLM 输出中提取 JSON（容忍 markdown 代码块包裹）"""
    # 去掉 ```json ... ``` 包裹
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试找第一个 { ... } 块
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


# =============================================================================
# 评分脚本生成 Prompt（被 routes_rubric 和 routes_ai 共同引用）
# =============================================================================

RUBRIC_SCRIPT_SYSTEM_PROMPT = """你是一位资深教育测评专家，擅长将评分规则转化为结构化的、无歧义的评分指令。

你的任务：根据提供的题目信息，生成一段【结构化评分脚本】。这段脚本将被保存并作为大模型自动阅卷时的**唯一评分依据**。评分时，阅卷模型只会看到这段脚本和考生答案，不会看到其他任何信息。

因此，评分脚本必须做到：
1. **完全自包含**：任何拿到脚本的人/模型，无需任何额外上下文就能准确评分
2. **跨系统一致**：不同机器、不同大模型（通义千问、智谱GLM、文心一言、豆包等）拿到同一脚本+同一答案，应给出相同分数
3. **容错性强**：能正确处理各种考生作答情况（完整答、部分答、用口语化表达、字很少、偏题、乱写等）

## 评分脚本的规范要求

### 1. 结构要求
评分脚本必须包含以下段落（按顺序）：

- 【题目信息】：完整复述题目内容和满分值（不要截断或省略）

- 【标准答案要点】：从标准答案中提炼出的核心要点，每个要点附带：
  - 要点的**核心含义**（用自己的话解释这个要点在说什么）
  - 要点的**关键词和表述方式**（考生可能怎么说）
  - 不要只列关键词，要把"为什么这是得分点"说清楚

- 【逐项评分规则】：每个得分点的判断标准，必须包含：
  - **得分条件**：什么情况下得满分，给出具体判断步骤（先检查什么，再检查什么）
  - **部分得分条件**：什么情况下得部分分，得多少，举例说明
  - **不得分条件**：什么情况下不得分
  - **易混淆判断**：哪些表述看起来相关但实际不应给分（防止误判）
  - 每个得分点必须同时列出：
    - 【必含关键词】至少 2 个，优先选择核心术语和专业名词
    - 【等价表述】至少 5 个，需覆盖以下维度：
      - 同义替换（如"促进"→"推动"/"助推"）
      - 上下位词（如"市场调节"→"价格机制"/"供求机制"）
      - 口语化表达（如"资源分配"→"把资源分到需要的地方"）
      - 部分匹配（如关键词单独出现也算命中）
      - 相关概念（如"市场配置资源"→"看不见的手"）

- 【反作弊规则】：明确以下情况直接判 0 分：
  - 复制题干内容作为答案
  - 答案为空或仅含标点
  - 答非所问（内容与题目完全无关）
  - 照抄标准答案以外的无关文本

- 【作答情况分类】：预先定义几种典型作答模式及其评分方式，例如：
  - 完整作答：覆盖所有要点→满分
  - 部分作答：只覆盖部分要点→按覆盖情况给分
  - 空白/无关：没答或答非所问→0分
  - 字数很少但关键：虽然字少但命中关键词→按规则正常给分

- 【扣分规则】（如有）：明确的扣分条件和幅度；如无扣分则写"本题无额外扣分项"

- 【总分计算】：总分 = 各项得分之和 - 扣分项，总分范围 [0, 满分]

- 【输出格式要求】：强制指定 JSON 输出格式

### 2. 语言要求
- **绝对禁止**使用以下模糊表述："酌情给分"、"视情况"、"根据质量"、"适当给分"、"可能给分"、"一般而言"、"通常"、"较好地"、"基本正确"
- **必须使用**确定性表述："如果...则得X分"、"只要提到...即得X分"、"未提到...则0分"、"包含...关键词得X分"、"当且仅当...得X分"
- 每个得分点的分值必须明确，不能有范围值
- 部分得分必须指定具体分值（如"只答对其中一个方面得1分"），不能说"酌情给0.5-1分"

### 3. 一致性保障
- 每个得分点使用**关键词匹配 + 语义匹配**双重判断
- 列出每个得分点的【必含关键词】（用于快速判断）
- 列出每个得分点的【等价表述】（用于语义匹配，至少3个）
- 明确区分"必须同时满足"和"满足其一即可"的条件
- 对于有多个子要点的得分点，明确写出"两个子要点都答对得X分，只答对一个得Y分"
- **关键**：关键词匹配优先于语义匹配。如果考生答案包含关键词，即使整体表述不理想也应给分

### 4. 抗干扰能力
- 脚本必须能区分"答对了"和"沾了点边但没答对"
- 对于概念类题目，明确区分"说出了概念名称"和"解释了概念含义"（有些题目要求解释，不能只写名称）
- 对于列举类题目，明确写出"列举N个要点得X分"，并标注哪些算同一个要点（防止同义重复计分）

### 5. 输出格式
- 生成的评分脚本本身就是一段结构化文本，不要用代码/函数形式
- 直接输出评分脚本内容，不要加任何解释"""
