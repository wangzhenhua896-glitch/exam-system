# 英语题目编辑器 UI 重构实现记录

> 实施日期: 2026-04-12 ~ 2026-04-14
> 分支: `multi-fullscore-answers`
> 设计方案: `docs/英语编辑器设计方案.md`

## 一、目标

为英语科目构建专用的题目编辑页面，采用 **5 步工作流**（解析 → 逐问配置 → 生成脚本 → 验证 → 保存），将 JSON 细节完全抽象化，教师只需操作表单和 Tag 芯片。

同时建立 **题型抽象层**（EDITOR_REGISTRY），为后续单选/多选/填空/判断题型扩展打下基础。

## 二、变更文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/models/db_models.py` | 已提交 + 继续修改 | 新增 `question_type` / `workflow_status` 列 + 对应 CRUD 函数 |
| `app/api_routes.py` | 已提交 + 继续修改 | 5 个新 API 端点 + 2 个辅助函数 |
| `app/english_prompts.py` | 已提交 | 675 行，英语科目全部 Prompt 模板 |
| `static/js/englishEditCore.js` | 已提交 + 继续修改 | ~989 行，英语编辑器核心模块（IIFE） |
| `templates/question-bank.html` | 已提交 + 继续修改 | 5 步工作流 UI（~330 行模板）+ setup() 集成 |
| `tests/test_english_edit.py` | 已提交 | 394 行，6 个测试类共 33 个测试用例 |

## 三、数据库层变更

### 3.1 新增列（ALTER TABLE 兼容旧库）

```sql
-- questions 表
ALTER TABLE questions ADD COLUMN question_type TEXT DEFAULT 'essay';  -- 题型标识
ALTER TABLE questions ADD COLUMN workflow_status TEXT DEFAULT NULL;   -- 工作流状态 JSON
```

### 3.2 新增/修改的 DB 函数（db_models.py）

| 函数 | 说明 |
|------|------|
| `add_question()` | 扩展支持 `question_type`、`workflow_status` 参数 |
| `update_question()` | 扩展支持 `question_type`、`workflow_status` 参数 |
| `update_workflow_status(question_id, status_json)` | 轻量级更新工作流状态，不触碰 rubric |

### 3.3 工作流状态存储策略

`workflow_status` 存为 questions 表的**独立列**，不存入 rubric JSON 中，避免保存评分脚本时覆盖工作流进度。

## 四、后端 API 变更

### 4.1 新增端点

| 方法 | 路径 | 功能 |
|------|------|------|
| PUT | `/api/questions/<id>/workflow-status` | 轻量更新工作流状态（不触发脚本快照） |
| POST | `/api/english/extract` | AI 提取子题 + 采分点（英语编辑器用） |
| POST | `/api/english/suggest-synonyms` | AI 同义词补全 |
| POST | `/api/english/suggest-exclude` | AI 排除词建议 |
| POST | `/api/english/generate-rubric` | AI 生成评分脚本（编辑器用） |

### 4.2 辅助函数

| 函数 | 说明 |
|------|------|
| `_call_llm_sync(system_prompt, user_prompt)` | 同步调用 LLM，3 次重试 |
| `_parse_json_from_llm(text)` | 从 LLM 返回文本中解析 JSON，容错 markdown 包裹 |

### 4.3 已有端点扩展

`POST /api/questions` 和 `PUT /api/questions/<id>` 已扩展支持 `question_type`、`workflow_status`、`rubric_rules`、`rubric_points`、`rubric_script` 字段。

## 五、前端架构

### 5.1 模块结构

```
templates/question-bank.html    ← 5 步工作流 UI 模板 + setup() 集成
static/js/englishEditCore.js    ← IIFE 模块，暴露 window.EnglishEditCore
```

**非 ES Module 模式**：通过 `<script>` 标签引入，用全局变量 `window.EnglishEditCore` 暴露接口。

### 5.2 核心：Vue.reactive 包装

```javascript
// setup() 中的关键一行
const englishEdit = Vue.reactive(window.EnglishEditCore.useEnglishEdit());
```

**踩坑记录**：`useEnglishEdit()` 返回的普通 JS 对象中嵌套的 Vue ref，在模板中**不会自动解包**。只有顶层 ref 或 `reactive()` 包装对象中的 ref 才会自动解包。这是导致白屏的根本原因（`completedSteps.indexOf is not a function` —— 因为 `completedSteps` 返回的是 ref 对象而非数组）。

### 5.3 useEnglishEdit() 暴露的状态和方法

**响应式状态**:
- `pageLoading`, `currentParentId`, `parentTitle`, `parentContent`, `parentMaxScore`
- `isStateA` — 是否有子题数据（State A: 有子题; State B: 仅有脚本）
- `currentStep`, `activeQuestionIndex`, `completedSteps`
- `subQuestions` — 子题数组，每项含 `questionText`, `standardAnswer`, `maxScore`, `scoringFormula`, `scoringPoints`, `excludeList`, `pinyinWhitelist`, `scoringRules`
- `generatedScript`, `validationResults`, `validationPassed`
- `extractingLoading`, `synonymLoadingMap`, `excludeLoading`, `scriptGenerating`
- `pasteText`, `rubricScript`

**计算属性**:
- `canEnterStep(stepId)` — 判断是否可进入某步
- `stepIndex` — 当前步骤索引
- `subScoreSum` — 子题满分之和
- `scoreMatch` — 子题满分之和是否等于父题满分

**核心方法**:
- `loadQuestion(id)` — 加载已有题目（区分 State A / B）
- `extractFromPaste()` — 粘贴原文 → AI 解析子题
- `addSubQuestion()` / `removeSubQuestion()`
- `addScoringPoint(qi)` / `removeScoringPoint(qi, pi)`
- `addScoringRule(qi, pi)` / `removeScoringRule(qi, pi, ri)`
- `suggestSynonyms(qi, pi)` — AI 同义词补全
- `suggestExclude(qi)` — AI 排除词建议
- `generateScript()` — AI 生成评分脚本
- `validateAll()` — 一致性验证
- `saveAll()` — 保存全部数据
- `buildApiPayload()` — 构建 API 请求 payload（必须满足 6 大格式约束）

### 5.4 buildApiPayload() 6 大格式约束

1. `score_formula` 必须是字符串（`"max_hit_score"` 或 `"hit_count"`），不是对象
2. `max_score` 必须存在
3. 每个 `scoring_point` 必须有 `id` 和 `score`
4. `rules` 必须嵌套在 `score_formula` 内
5. `keywords` 应为小写
6. 字段名必须完全匹配（`keywords`/`synonyms`/`exclude_list`/`pinyin_whitelist`）

### 5.5 Tag 芯片交互

- 输入框回车 → 添加芯片
- 粘贴逗号/顿号分隔文本 → 批量添加
- 芯片上 × → 删除
- `addTag(list, value)` / `removeTag(list, index)` / `addTagsFromPaste(list, text)`

## 六、5 步工作流 UI

| 步骤 | ID | 功能 | UI 元素 |
|------|----|------|---------|
| Step 1 | `extract` | 原题解析 | 文本粘贴区 + "智能解析"按钮 + 手动创建入口 |
| Step 2 | `per_question` | 逐小问配置 | 子题卡片（Q1/Q2/Q3）+ 采分点编辑 + Tag 芯片 + AI 补全按钮 |
| Step 3 | `script` | 评分脚本生成 | "生成脚本"按钮 + 脚本预览区 |
| Step 4 | `validate` | 一致性验证 | V1-V9 检查结果展示 |
| Step 5 | `save` | 保存 | 汇总信息 + "保存"按钮 |

### 步骤导航守卫

- `canEnterStep(stepId)` 基于 `completedSteps` 数组判断
- `goToStep(stepId)` 切换当前步骤
- `completeCurrentQuestion()` 标记当前子题完成
- 步骤指示器高亮当前步骤 + 完成标记

## 七、题型抽象层设计

### EDITOR_REGISTRY 注册表

```javascript
const EDITOR_REGISTRY = {
  essay:         { component: 'EssayEditor',     load: loadEssay,     save: saveEssay,     validate: validateEssay },
  single_choice: { component: 'ChoiceEditor',    load: loadChoice,    save: saveChoice,    validate: validateChoice },
  multi_choice:  { component: 'ChoiceEditor',    load: loadMultiChoice, save: saveMultiChoice, validate: validateMultiChoice },
  fill_blank:    { component: 'FillBlankEditor',  load: loadFillBlank, save: saveFillBlank, validate: validateFillBlank },
  true_false:    { component: 'TrueFalseEditor',  load: loadTrueFalse, save: saveTrueFalse, validate: validateTrueFalse },
};
```

**统一接口签名**：所有题型编辑器实现 `load(id)` / `save(formData)` / `validate(formData)` 三个方法。

**后端路由策略**：`three_layer_grader.py` 按 `rubric.type` 分流到不同评分函数：
- `single_choice` / `multi_choice` / `fill_blank` / `true_false` → 确定性判分（无 LLM）
- `essay`（默认）→ 现有三层并行评分

**数据存储策略**：不新建表，用现有字段承载不同题型数据：
- `questions.rubric` → 存储题型元数据（含 `type` 字段）
- `question_answers` → 用 `scope_type` 区分存储题型特定数据（选项列表、空位答案等）

## 八、Prompt 设计（english_prompts.py）

### 编辑器专用 Prompt

| Prompt | 用途 |
|--------|------|
| `EXTRACT_SUBQUESTIONS_SYSTEM` | 从原文提取子题 + 采分点，输出 JSON Schema |
| `SUGGEST_SYNONYMS_SYSTEM` | 同义词补全，含置信度评分，过滤 confidence < 0.5 |
| `SUGGEST_SYNONYMS_SYSTEM` | 排除词建议 |
| `GENERATE_RUBRIC_SCRIPT_SYSTEM` | 从采分点配置生成评分脚本 |

### 从 api_routes.py 迁移的 Prompt

- `RUBRIC_SCRIPT_SYSTEM_PROMPT_EN` — 评分脚本生成
- `QUALITY_EVALUATION_SYSTEM_PROMPT_EN` — 命题质量评估
- `SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN` — 脚本自查
- `GRADING_SYSTEM_PROMPT_EN` — 评分提示词
- `AUTO_GEN_QUESTION_SYSTEM_EN` / `AUTO_GEN_TESTCASE_SYSTEM_EN` — 自动出题/测试用例

## 九、测试覆盖

`tests/test_english_edit.py` — 6 个测试类共 33 个用例：

| 测试类 | 用例数 | 覆盖内容 |
|--------|--------|----------|
| TestDbMigration | 5 | question_type / workflow_status 列存在性、默认值、更新 |
| TestWorkflowStatusUpdate | 2 | update_workflow_status() 函数、不覆盖 rubric |
| TestApiValidation | 6 | 5 个新端点的参数校验 + 错误方法测试 |
| TestBuildApiPayloadFormat | 9 | buildApiPayload 6 大格式约束的 Python 端验证 |
| TestEnglishPrompts | 5 | Prompt 模块导入和基本调用 |
| TestParseJsonFromLlm | 6 | JSON 解析鲁棒性（纯文本、markdown 包裹、无效格式、嵌套） |

**状态**：已运行，33/33 全部通过（2026-04-14）。

## 十、踩坑记录

### 10.1 Vue 3 ref 嵌套白屏（P0）

**现象**：页面完全白屏，控制台报 `completedSteps.indexOf is not a function`。

**根因**：`useEnglishEdit()` 返回普通 JS 对象，其中 `completedSteps` 是 `Vue.ref([])`。Vue 3 模板中，只有**顶层 ref** 或 **reactive() 对象中的 ref** 才会自动解包。嵌套在普通对象中的 ref 不会自动解包，导致模板拿到的是 ref 对象而非数组。

**修复**：在 `question-bank.html` 的 setup() 中用 `Vue.reactive()` 包装：
```javascript
const englishEdit = Vue.reactive(window.EnglishEditCore.useEnglishEdit());
```

**诊断过程**：安装 Playwright → 发现登录重定向 → 设置 localStorage 绕过 → 捕获运行时错误 → 定位根因。

### 10.2 Playwright 测试环境

- 需要 `npm install playwright`（系统有 playwright CLI 但缺 npm 包）
- 管理页面有登录守卫，需先设置 `localStorage.setItem('ai_grading_current_subject', 'english')`

## 十一、待完成事项

### 高优先级

1. ~~**运行后端测试**~~ — ✅ 已完成，33/33 全部通过
2. ~~**提交 3 个未跟踪文件**~~ — ✅ 已在 a067a34 中提交
3. ~~**同义词/排除词自动填入**~~ — ✅ 已实现为点击添加模式（el-popover 逐个/批量添加，已有词灰显去重）
4. **端到端测试** — 完整走通 Step 1 → Step 5 的工作流

### 中优先级

5. **采分点提取专用端点** — 当前 `extractScoringPoints()` 复用 `/api/english/extract`，效果可能不够精准
6. **质量评估集成** — `QUALITY_EVALUATION_SYSTEM_PROMPT_EN` 已存在但未接入工作流
7. **自查步骤集成** — `SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN` 已存在但未接入

### 低优先级

8. **State B 加载验证** — 仅有 rubric_script 无子题数据的旧题目加载逻辑
9. **题型编辑器扩展** — EDITOR_REGISTRY 已就位，ChoiceEditor / FillBlankEditor / TrueFalseEditor 待实现
10. **测试依赖清理** — `test_workflow_status_requires_body` 依赖题目 ID=1 存在，应改为 fixture

## 十二、与设计方案的对照

| 设计方案要求 | 实现状态 |
|-------------|---------|
| 5 步工作流（extract → per_question → script → validate → save） | ✅ 已实现 |
| Tag 芯片交互（回车添加、粘贴批量、×删除） | ✅ 已实现 |
| AI 同义词补全按钮 | ✅ 已实现，点击添加 + 全部添加 + 已有词灰显去重 |
| AI 排除词建议按钮 | ✅ 已实现，点击添加 + 全部添加 + 已有词灰显去重 |
| 评分公式切换（max_hit_score / hit_count） | ✅ 已实现 |
| buildApiPayload 6 大约束 | ✅ 已实现 |
| 题型抽象层 EDITOR_REGISTRY | ✅ 注册表已就位，仅 essay 实现 |
| workflow_status 独立列存储 | ✅ 已实现 |
| State A / State B 双轨加载 | ✅ 已实现 |
| 质量评估 + 自查步骤 | ❌ 未接入 |
