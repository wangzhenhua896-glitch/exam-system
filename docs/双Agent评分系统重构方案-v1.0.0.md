# 双Agent评分系统重构方案

> **文档版本**: v1.0.0
> **最后更新**: 2026-04-10
> **状态**: 设计完成，待实施
> **维护者**: AI Grading System Team

---

## 目录

1. [问题分析](#1-问题分析)
2. [核心思路](#2-核心思路)
3. [新架构流程](#3-新架构流程)
4. [预处理模块设计](#4-预处理模块设计)
5. [阅卷Agent改造](#5-阅卷agent改造)
6. [判别Agent设计](#6-判别agent设计)
7. [流水线编排器](#7-流水线编排器)
8. [科目策略体系](#8-科目策略体系)
9. [文件变更清单](#9-文件变更清单)
10. [数据库变更](#10-数据库变更)
11. [API兼容性](#11-api兼容性)
12. [前端变更](#12-前端变更)
13. [实施步骤](#13-实施步骤)
14. [风险与缓解](#14-风险与缓解)
15. [验证方式](#15-验证方式)

---

## 1. 问题分析

| 编号 | 问题现象 | 根因推测 |
|------|----------|----------|
| P1 | 同一答案多次评分,分数不一致(温度已设0.1) | LLM采样随机性 + 单次调用缺乏自校验 |
| P2 | 未作答的情况下给出满分 | 提示词未强制空答案校验 + 模型幻觉 |
| P3 | 删除一个评分点后仍满分,评价中出现未答内容 | 疑似上下文缓存/对话历史污染/提示词模板泄漏 |
| P4 | 相近答案应给80%却实际偏离目标分 | 整体打分粒度太粗,未按评分点独立判定 |

**深层原因**:
1. 温度0.1不等于分数稳定
2. 提示词让模型一次性做了太多事(读题→找评分点→判断命中→算总分),任何一步飘了总分就变
3. 评分标准本身有模糊地带(如"语意相近即可"),模型每次对"相近"的边界判断不同
4. 输出格式是自由文本,模型自己在凑一个合理的总分

---

## 2. 核心思路

**架构原则**：建立知识库，设立两个Agent多轮博弈，答案聚类预处理，按原子评分点切分式判定。

- **阅卷Agent**：只负责在学生答案中寻找并提取与评分标准匹配的"原话（证据）"，不做任何打分决定，不计算总分
- **判别Agent**：拿着阅卷Agent提交的"证据"，对照原始学生答案和评分细则进行二次交叉验证，揪出幻觉，输出最终得分档位，也不计算总分
- **后端Python代码**：累加各评分点得分，由系统计算总分

---

## 3. 新架构流程

```
POST /api/grade
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  预处理模块 (Preprocessor) — 纯Python，不调LLM            │
│  ├─ 空答案检测 → 直接0分，不触发后续                       │
│  ├─ 敏感词检测（思政题）                                   │
│  ├─ 评分规则拆解为"原子评分点"                             │
│  ├─ 子问题识别（第1问、第2问）                             │
│  ├─ 答案分段匹配                                          │
│  └─ 字数检查                                              │
└────────────────────┬────────────────────────────────────┘
                     │ should_skip_llm?
                     ├─ Yes → 返回0分（跳过后续所有步骤）
                     │
                     ▼ No
┌─────────────────────────────────────────────────────────┐
│  阅卷Agent (ReadingAgent) — 改造现有QwenGradingEngine     │
│  ├─ 只提取证据，不计算总分                                 │
│  ├─ 固定JSON输出：{point_id, hit, score, reason, quoted}  │
│  ├─ 子问题模式：每问独立调用LLM                            │
│  └─ 纯函数：无外部状态依赖，无对话历史                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  判别Agent (ValidatorAgent) — 纯Python规则引擎，不调LLM    │
│  ├─ 证据真实性：quoted_text是否真实存在于原始答案中          │
│  ├─ 空白答案+满分 → 标记异常                               │
│  ├─ 与上次评分差值>20% → 标记缓存污染                      │
│  └─ 分数分布异常检测                                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  后端总分计算器 (Calculator) — 纯Python累加                │
│  ├─ 各评分点得分求和                                      │
│  ├─ 聚类组内取中位数                                      │
│  └─ 分数截断到 [0, max_score]                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
              返回 JSON 响应（向后兼容）
```

---

## 4. 预处理模块设计

### 4.1 数据结构

```python
@dataclass
class AtomicScoringPoint:
    """一个原子评分点"""
    point_id: str                    # "sp_1", "sp_2"
    name: str                        # "答出矛盾的普遍性"
    full_score: float                # 该点分值
    keywords: List[str]              # 关键词列表
    synonyms: List[str]              # 同义词对照表
    special_rules: str               # 特殊规则（如"未体现主体地位不得分"）
    sub_question: Optional[str]      # 所属子问题（如"第1问"）
    partial_score_rules: Dict[str, float]  # 部分得分规则

@dataclass
class SubQuestion:
    """一个子问题"""
    label: str                       # "第1问", "(1)", "(2)"
    text: str                        # 子问题文本
    matched_points: List[str]        # 关联的原子评分点point_id
    answer_segment: Optional[str]    # 对应的学生答案片段

@dataclass
class PreprocessorResult:
    """预处理输出"""
    should_skip_llm: bool            # 是否跳过LLM直接判分
    skip_reason: str                 # "empty_answer" / "sensitive_words"
    skip_score: float                # 跳过时的分数（通常0）
    subject_strategy: str            # "politics" / "chinese" / "english" / "general"
    sub_questions: List[SubQuestion]
    atomic_points: List[AtomicScoringPoint]
    answer_segments: Dict[str, str]  # {sub_label: answer_text}
    is_structured: bool              # 答案是否有编号分段
    word_count: int
    warning: Optional[str]
```

### 4.2 process() 流程

1. **空答案检测**：去除空格后长度 < 2 → `should_skip_llm=True`, `skip_score=0`
2. **加载科目策略**：根据 subject 字段加载对应策略
3. **敏感词检测**（思政题）：触发则 `should_skip_llm=True`
4. **字数检查**：是否在建议字数内，作为辅助参数传给阅卷Agent
5. **评分规则拆解**：将 rubric 拆解为独立的原子评分点
   - 英语题：区分"核心信息点（70%）"和"语法拼写点（30%）"
   - 思政题：每个得分要素单独建档
6. **子问题识别**：正则匹配 "第X问"、"(X)"、"X." 等模式
7. **答案分段**：按序号拆分学生答案，无序号则标记"非结构化"，全文作为整体

### 4.3 答案聚类（向量嵌入分组）

- 对同一题目的所有学生答案做向量嵌入
- 按余弦相似度分组，按答案长度分档设阈值：
  - 短答案 (<20字符): 阈值 0.95
  - 中等 (20~100字): 阈值 0.90
  - 长答案 (>100字): 阈值 0.85
- 同组内答案被视为"语义等价"，统一送入一次LLM调用
- 取中位数作为该组代表分

---

## 5. 阅卷Agent改造

### 5.1 改造要点

改造 `app/qwen_engine.py`，新增 `extract_evidence()` 方法：

- **提示词重写**：不再要求"打分"，而是"逐个评分点提取原文证据"
- **输出格式固定**：严格JSON schema，禁止自由格式文本
- **评分点结构化传入**：原子评分点（含关键词/同义词/分值）作为输入
- **纯函数架构**：不依赖任何外部状态，不把上一个学生的答案或评分结果作为历史记录传给模型
- **阶梯式降级匹配**：放弃"相近给80%"，改用"完全包含关键词A和B→2分，只包含外延词C→1分，否则0分"
- **迷惑性示例**：在提示词中加入几个极具迷惑性的错误答案示例

### 5.2 新输出格式

```json
{
  "items": [
    {
      "point_id": "sp_1",
      "hit": true,
      "score": 2.0,
      "reason": "提到了矛盾的普遍性",
      "quoted_text": "矛盾是普遍存在的",
      "confidence": "high"
    },
    {
      "point_id": "sp_2",
      "hit": false,
      "score": 0,
      "reason": "未提及矛盾的特殊性",
      "quoted_text": "",
      "confidence": "high"
    }
  ],
  "comment": "简要评语（不超过100字）"
}
```

**关键约束**：
- 禁止输出总分
- 禁止输出自由格式文本
- 禁止"酌情给分"类判断
- `quoted_text` 必须是学生答案中的原文，不可编造
- 只要求AI判定"采分点1是否得分"、"采分点2是否得分"，由后端系统进行加法计算得出总分

### 5.3 子问题模式

对于一题多问，在程序逻辑层进行预处理，拆解为多个独立的子任务单元：

1. 首先在学生完整答案中定位与第几小题相关的文本区块
2. 忽略与子题无关的内容
3. 从定位到的区块中提取答案
4. 如果学生未标明题号，根据语义逻辑判断哪一部分是针对本小题的回答
5. 每个子问题看作独立的评分会话，只提供该小题对应的评分标准

---

## 6. 判别Agent设计

### 6.1 核心职责

**纯Python规则引擎**，不调LLM，所有检查都是确定性的字符串匹配和算术。

### 6.2 检查项

| 检查项 | 解决的问题 | 实现方式 |
|--------|-----------|----------|
| **证据真实性验证** | P3（缓存幻觉） | `quoted_text in original_answer` 精确匹配，不命中则强制该点0分 |
| **空白答案+满分** | P2（空答案满分） | 答案长度<5字符但有得分 → 标记异常，触发重评 |
| **评分一致性** | P1（分数不一致） | 与同题上次评分差值 > 20% → 标记疑似缓存污染，清空上下文重评 |
| **标准差阈值检验** | P1 + 聚类质量 | 组内 σ > 阈值(0.5分) → 细分重评；两次仍超标 → 标记人工复核 |
| **异常检测规则** | 综合 | 专门针对已知问题设计硬规则，在LLM返回结果后立即过滤 |

### 6.3 标准差阈值检验流程

1. 对每组内的评分结果计算标准差 σ
2. σ ≤ 阈值(建议初始值0.5分) → 组内抹平，确认中位数为最终分
3. σ > 阈值 → 说明该组聚类质量差，将组内答案重新细分再送阅卷Agent
4. 若两次σ仍超阈值 → 标记为"需人工复核"

---

## 7. 流水线编排器

### 7.1 GradingPipeline 类

```python
class GradingPipeline:
    def __init__(self, engine: QwenGradingEngine, config: Dict):
        self.engine = engine
        self.preprocessor = Preprocessor()
        self.validator = ValidatorAgent(config)

    async def run(self, question, answer, rubric, max_score,
                  subject="general", question_id=None) -> PipelineResult:
        # Stage 1: 预处理
        prep = self.preprocessor.process(...)
        if prep.should_skip_llm:
            return PipelineResult(score=0, ...)

        # Stage 2: 阅卷Agent (LLM)
        if prep.is_structured and len(prep.sub_questions) > 1:
            evidence = await self._grade_by_sub_questions(prep)
        else:
            evidence = await self.engine.extract_evidence(...)

        # Stage 3: 判别Agent
        validation = self.validator.validate(answer, evidence.items, ...)

        # Stage 4: 后端计算总分
        total_score = sum(item["score"] for item in validation.verified_items)
        total_score = round(max(0, min(total_score, max_score)), 2)

        return PipelineResult(score=total_score, ...)
```

### 7.2 PipelineResult

```python
@dataclass
class PipelineResult:
    score: float
    confidence: float
    comment: str
    scoring_items: List[Dict]        # 各评分点得分明细
    needs_review: bool               # 是否需要人工复核
    warning: Optional[str]
    evidence: List[Dict]             # 阅卷Agent原始证据
    validation_flags: List[Dict]     # 判别Agent标记
    pipeline_stages: Dict[str, float]  # 各阶段耗时
```

---

## 8. 科目策略体系

### 8.1 题型策略矩阵

| 题型 | 匹配策略 | 特殊规则 |
|------|----------|----------|
| **思政** | 逐点关键词命中 + 语义相似度 | 违背主流价值观直接0分 |
| **语文** | 逐点关键词命中 + 语义相似度 | 主观题以参考答案为基准，给区间分 |
| **英语** | 核心词优先 | 轻微语法/拼写不扣分，同义词兼容 |

### 8.2 英语题评分权重

- 核心信息点：70%
- 语法拼写点：30%

### 8.3 思政题特殊处理

- 预处理阶段检索敏感词库
- 触发严重的价值观违规 → 直接打标"全题0分预警"
- 反作弊规则优先于所有评分规则

---

## 9. 文件变更清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `app/preprocessor.py` | 预处理模块：空答案检测、评分规则拆解、子问题识别、答案分段、敏感词检测 |
| `app/validator_agent.py` | 判别Agent：证据真实性验证、异常检测、一致性检查 |
| `app/grading_pipeline.py` | 流水线编排器：串联 Preprocessor → ReadingAgent → Validator → Calculator |
| `app/strategies/base.py` | 科目策略基类 |
| `app/strategies/politics.py` | 思政题策略：敏感词库、反作弊规则 |
| `app/strategies/chinese.py` | 语文题策略 |
| `app/strategies/english.py` | 英语题策略 |
| `app/strategies/__init__.py` | 策略注册 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/qwen_engine.py` | 新增 `extract_evidence()` 方法；改造提示词；固定JSON输出格式；保留 `grade()` 作为兼容wrapper |
| `app/api_routes.py` | `grade_answer()` 内部改用 `GradingPipeline.run()`；加 `DUAL_AGENT_MODE` 特性开关 |
| `app/models/db_models.py` | `grading_records` 表新增 `grading_flags` 和 `evidence_data` 列；修改 `add_grading_record()` |
| `dist/index.html` | 评分结果区展示证据引用原文 + 验证标记 |
| `config/settings.py` | 新增预处理/验证配置常量 |

---

## 10. 数据库变更

`grading_records` 表新增两列（在 `init_database()` 中用现有 try/except ALTER TABLE 模式迁移）：

```sql
ALTER TABLE grading_records ADD COLUMN grading_flags TEXT DEFAULT NULL;
ALTER TABLE grading_records ADD COLUMN evidence_data TEXT DEFAULT NULL;
```

- `grading_flags`：存储判别Agent的验证标记JSON数组，用于调试和审计
- `evidence_data`：存储阅卷Agent的原始证据JSON，用于审计

---

## 11. API兼容性

`POST /api/grade` 输入输出格式**完全向后兼容**。

### 新增响应字段（纯增量，不破坏现有字段）

```json
{
  "success": true,
  "data": {
    "score": 8.0,
    "confidence": 0.85,
    "comment": "...",
    "details": {
      "scoring_items": [
        {
          "name": "得分点1",
          "score": 2,
          "max_score": 2,
          "hit": true,
          "reason": "...",
          "evidence": "学生原文引用"
        }
      ],
      "validation_flags": [
        {"type": "...", "severity": "info", "desc": "..."}
      ],
      "pipeline_stages": {
        "preprocess": 0.01,
        "reading_agent": 2.3,
        "validator": 0.02,
        "calculate": 0.001
      }
    },
    "model_used": "dual-agent",
    "needs_review": false,
    "warning": null
  }
}
```

- `details.scoring_items[].evidence` — 引用的原文证据（新增）
- `details.validation_flags` — 验证标记数组（新增）
- `details.pipeline_stages` — 各阶段耗时（新增）
- `model_used` 从 `"qwen-agent"` 变为 `"dual-agent"`

---

## 12. 前端变更

`dist/index.html` 变更最小化，纯增量：

1. **证据展示**：scoring_items 区域新增折叠的"证据"部分，展示 `item.evidence`（引用原文）
2. **验证标记展示**：warning 区域之后新增 el-alert 展示 validation_flags
3. **流水线耗时**（调试用）：在原始详情折叠区自动可见

---

## 13. 实施步骤

### Phase 1: 预处理模块（低风险，独立）

**文件**: `app/preprocessor.py`, `app/strategies/`

1. 创建 `app/preprocessor.py`，实现 `Preprocessor` 类和所有 dataclass
2. 创建 `app/strategies/` 目录，实现 base 和 politics 策略
3. 以 logging-only 模式集成到 `grade_answer()`：运行预处理并记录结果，但不影响评分
4. 验证：空答案检测准确性

### Phase 2: 改造 ReadingAgent（中风险，核心变更）

**文件**: `app/qwen_engine.py`

1. 新增 `extract_evidence()` 方法，含新提示词和输出schema
2. 新增 `_parse_evidence_output()`，严格JSON schema验证
3. 新增 `_build_evidence_user_prompt()`，原子评分点作为结构化输入
4. 保留 `grade()` 作为兼容wrapper（内部调用 `extract_evidence()` 并累加分数）
5. 验证：一致性测试对比新旧实现

### Phase 3: 判别Agent（低风险，独立）

**文件**: `app/validator_agent.py`

1. 实现 `ValidatorAgent` 类，含所有四项检查
2. 单元测试：注入伪造引用→验证被捕获；空白答案+满分→验证异常标记
3. 验证：用真实评分输出测试

### Phase 4: 流水线集成（高风险，串联所有模块）

**文件**: `app/grading_pipeline.py`, `app/api_routes.py`, `app/models/db_models.py`

1. 创建 `app/grading_pipeline.py`
2. `grade_answer()` 加 `DUAL_AGENT_MODE` 环境变量特性开关（默认 `false`）
3. 数据库迁移：新增 `grading_flags` 和 `evidence_data` 列
4. 修改 `add_grading_record()` 接收并存储新字段
5. 验证：A/B 测试新旧流水线

### Phase 5: 前端更新（低风险）

**文件**: `dist/index.html`

1. 证据展示
2. 验证标记展示
3. 视觉测试

---

## 14. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 新提示词质量下降 | 评分结果回退 | Phase 2 做A/B对比，保留旧 `grade()` 降级 |
| 子问题解析失败 | 非结构化答案出错 | `is_structured=False` 时自动降级为单次调用 |
| 判别Agent误报 | 不必要的人工复核 | 用精确字符串匹配（非模糊匹配），消除假阳性 |
| 延迟增加 | 用户等待更久 | 预处理<10ms，判别<50ms，仅LLM调用耗时；子问题模式总延迟相当 |
| 特性开关未充分测试 | 生产评分中断 | `DUAL_AGENT_MODE` 默认 `false`，旧代码路径不受影响 |
| 原子评分点拆解不准 | 过细或过粗 | 拆解失败时降级为整体评分（与当前行为一致） |
| 缓存幻觉未完全解决 | 判别Agent漏检 | `quoted_text in original_answer` 精确匹配，编造一个字节也会被捕获 |

---

## 15. 验证方式

| 验证类型 | 方法 |
|----------|------|
| **单元测试** | 预处理模块、判别Agent各检查项的独立测试 |
| **一致性测试** | 同一答案多次评分，验证分数完全一致 |
| **边界测试** | 空白答案→0分；删除评分点→总分下降；复制原文→0分 |
| **A/B对比** | 新旧流水线对同一批测试用例的评分结果对比 |
| **端到端** | 通过 `/test-cases` 页面的验证功能跑完整流程 |
| **压力测试** | 批量评分，验证延迟和并发表现 |

---

**文档结束**

如有问题或建议，请联系维护团队。
