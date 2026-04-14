# AI 智能评分系统 - 项目文档

## 1. 项目概述

基于国产大模型（通义千问 Qwen 为主力）的简答题自动化评分系统。面向职业学校对口升学考试，核心目标是**评分脚本驱动的高一致性评分**。

| 项目 | 说明 |
|------|------|
| **版本** | v2.0.0 |
| **技术栈** | Python 3.12 + Flask 3.0 + SQLite + Vue 3 + Element Plus |
| **服务端口** | 5005 |
| **数据库** | SQLite (`data/exam_system.db`) |
| **评分引擎** | QwenGradingEngine（单模型，temperature=0.0） |

### 访问地址

| 页面 | 地址 | 说明 |
|------|------|------|
| 题库管理 | http://localhost:5005/management | Vue 3 + Element Plus SPA |
| 聚焦评分 | http://localhost:5005/grading | 暗色主题 Vanilla JS |

---

## 2. 目录结构

```
ai-grading-system/
├── main.py                    # 入口：启动 Flask，端口 5005
├── requirements.txt           # Python 依赖
├── start.sh                   # 快速启动脚本
├── .env                       # API 密钥（不入库）
├── .env.example               # 环境变量模板
│
├── app/
│   ├── __init__.py            # 包初始化，version "2.0.0"
│   ├── app.py                 # Flask 应用工厂，路由注册
│   ├── api_routes.py          # 主 API（题目、评分、大纲、测试用例）
│   ├── qwen_engine.py         # 评分引擎（核心）
│   ├── routes.py              # 【遗留】多模型聚合评分路由
│   ├── batch_routes.py        # 【遗留】批量评分路由
│   ├── validation_routes.py   # 【遗留】规则验证路由
│   ├── tuning_routes.py       # 【遗留】自动调优路由
│   ├── engine.py              # 【遗留】多模型聚合引擎
│   ├── validation.py          # 【遗留】验证引擎
│   ├── auto_tuning.py         # 【遗留】自动调优引擎
│   ├── test_data.py           # 硬编码测试数据集
│   └── models/
│       ├── __init__.py
│       ├── base.py            # 抽象 BaseModelClient
│       ├── registry.py        # 模型注册表（单例）
│       ├── qwen.py            # 通义千问客户端
│       ├── glm.py             # 智谱 GLM 客户端
│       ├── ernie.py           # 百度文心客户端
│       ├── minimax.py         # MiniMax 客户端
│       └── doubao.py          # 字节豆包客户端
│
├── config/
│   └── settings.py            # 模型配置、评分配置、服务配置
│
├── templates/
│   ├── question-bank.html     # 题目列表 + 英语编辑器（~1087 行）
│   ├── question-edit.html     # 题目编辑（1459 行）
│   ├── dedup.html             # 去重合并（524 行）
│   ├── import.html            # 导入题目（392 行）
│   ├── ai-generate.html       # AI 批量出题（175 行）
│   ├── syllabus.html          # 考试大纲/教材（204 行）
│   ├── export-rubrics.html    # 导出评分脚本（~135 行）
│   ├── consistency-check.html # 一致检查（~158 行）
│   ├── login.html             # 登录
│   ├── test-cases.html        # 测试集管理
│   ├── sensitive-words.html   # 敏感词管理
│   ├── user-management.html   # 用户管理
│   └── admin.html             # 管理后台
│
├── dist/
│   └── index.html             # 暗色主题评分页（~630 行）
│
├── data/
│   └── exam_system.db         # SQLite 数据库
│
├── docs/
│   └── PROJECT_SUMMARY.md     # 本文档
│
├── static/                    # 基础样式和脚本（未使用）
├── tests/                     # 空测试目录
└── logs/                      # 评分日志
```

### 重要说明

- **活跃代码**：`api_routes.py` + `qwen_engine.py` 是当前实际使用的后端
- **遗留代码**：`routes.py`、`batch_routes.py`、`validation_routes.py`、`tuning_routes.py`、`engine.py` 等是早期多模型聚合方案的遗留，对应的前端页面已标记为"暂未开放"
- **端口不一致**：`main.py` 硬编码 5005，`start.sh` 写 5000，`settings.py` 默认 5001。以 `main.py` 为准

---

## 3. 数据库设计

SQLite，共 6 张表：

### questions（题目）
```sql
CREATE TABLE questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject         TEXT NOT NULL,           -- 学科标识（politics, chinese 等）
    title          TEXT NOT NULL,            -- 标题（取内容前30字）
    content        TEXT NOT NULL,            -- 题干（处理后）
    original_text  TEXT,                     -- 原始未处理文本
    standard_answer TEXT,                    -- 标准答案
    rubric_rules   TEXT,                     -- 评分规则（整体描述）
    rubric_points  TEXT,                     -- 分数分布（每行一个得分点）
    rubric_script  TEXT,                     -- AI 生成的结构化评分脚本
    rubric         TEXT NOT NULL,            -- JSON 聚合字段
    max_score      REAL DEFAULT 10.0,        -- 满分值
    quality_score  REAL DEFAULT NULL,        -- AI 质量评估分数（0-100）
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`rubric` 字段存储 JSON，结构：
```json
{
    "rubricRules": "评分规则文本",
    "points": [{"description": "得分点描述"}],
    "rubricScript": "结构化评分脚本",
    "knowledge": "知识点",
    "contentType": "简答题",
    "aiPrompt": "评分提示词",
    "standardAnswer": "标准答案"
}
```

### test_cases（测试用例）
```sql
CREATE TABLE test_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id     INTEGER NOT NULL,
    answer_text     TEXT NOT NULL,            -- 考生作答内容
    expected_score  REAL NOT NULL,            -- 期望分数
    description     TEXT DEFAULT '',          -- 描述
    case_type       TEXT DEFAULT 'simulated', -- simulated/real
    last_actual_score REAL DEFAULT NULL,      -- 上次验证的实际分数
    last_error      REAL DEFAULT NULL,        -- 上次验证的误差
    last_run_at     TIMESTAMP DEFAULT NULL,   -- 上次验证时间
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### grading_records（评分记录）
```sql
CREATE TABLE grading_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id     INTEGER,
    student_answer  TEXT NOT NULL,
    score           REAL,
    details         TEXT,                     -- JSON 评分详情
    model_used      TEXT,
    confidence      REAL,
    graded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### syllabus（考试大纲/教材）
```sql
CREATE TABLE syllabus (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject         TEXT NOT NULL,
    content_type    TEXT NOT NULL,            -- syllabus/textbook
    title           TEXT NOT NULL DEFAULT '',
    content         TEXT NOT NULL DEFAULT '',
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subject, content_type)
);
```

### 其他表
- `rubrics` — 已定义但未在路由中使用
- `batch_tasks` — 批量任务，遗留使用

---

## 4. 评分引擎（qwen_engine.py）

### QwenGradingEngine

核心评分类，单模型 + deterministic 输出。

**评分流程：**
1. `_format_rubric()` — 格式化评分规则，优先使用 `rubricScript`，降级到 rules + points + knowledge + standardAnswer
2. 构建 system prompt — 要求 LLM 扮演严格阅卷老师，逐项评分，输出 `{"总分": X, "评语": "..."}`
3. LLM 调用 — `temperature=0.0`，同步 OpenAI 客户端
4. `_parse_output()` — JSON 提取 + 正则 fallback
5. `_calculate_confidence()` — 基于输出长度计算置信度
6. `boundary_check()` — 边界检测：≥95% 或 ≤5% 满分预警，低置信度标记

**模型优先级：** Qwen > GLM > ERNIE > Doubao > Xiaomi Mimimo > 环境变量 fallback

### 关键设计：评分脚本（rubric_script）

评分脚本是本系统的核心创新，是针对每道题编写的**结构化、确定性评分指令**。要求：
- 非重叠的评分要点（A/B/C/D）
- 每个要点附带正例和反例
- 强制 JSON 输出格式
- 关键区分规则（避免歧义）

通过测试用例验证可以迭代改进脚本，直到 100% 通过率。

---

## 5. API 端点（api_routes.py）

### 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/questions` | 列表，支持 `?subject=` 过滤 |
| GET | `/api/questions/<id>` | 详情 |
| POST | `/api/questions` | 新建 |
| PUT | `/api/questions/<id>` | 更新 |
| DELETE | `/api/questions/<id>` | 删除（级联删除测试用例） |

### 评分

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/grade` | 单题评分（核心） |
| POST | `/api/generate-rubric-script` | AI 生成评分脚本 |
| POST | `/api/evaluate-question` | AI 题目质量评估 |

### 测试用例

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/questions/<id>/test-cases` | 列出测试用例 |
| POST | `/api/questions/<id>/test-cases` | 添加测试用例 |
| PUT | `/api/questions/<id>/test-cases/<tc_id>` | 更新 |
| DELETE | `/api/questions/<id>/test-cases/<tc_id>` | 删除 |
| POST | `/api/verify-rubric` | 运行所有测试用例验证评分脚本 |

### 考试大纲

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/syllabus` | 列表 |
| GET | `/api/syllabus/<subject>/<type>` | 详情 |
| POST | `/api/syllabus` | 保存（upsert） |
| DELETE | `/api/syllabus/<subject>/<type>` | 删除 |

### 统计/历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 仪表盘统计 |
| GET | `/api/history` | 评分历史，支持 `?question_id=&limit=` |

---

## 6. 前端架构

### 6.1 题库管理 — 多页面架构

`question-bank.html` 曾为 3653 行巨型单文件，经 8 轮拆分后降至 **~898 行**，功能分散到 10 个独立页面：

| 页面 | 路由 | 文件 | 行数 | 功能 |
|------|------|------|------|------|
| 题库管理 | `/management` | question-bank.html | ~898 | 题目列表 + 英语编辑器 |
| 题库总览 | `/dashboard` | dashboard.html | ~180 | 统计卡片、覆盖率、质量分布、趋势 |
| 题目详情 | `/question-view` | question-view.html | ~90 | 查看题目详情 |
| 题目编辑 | `/question-edit` | question-edit.html | 1459 | 新建/编辑/查看题目 |
| 去重合并 | `/dedup` | dedup.html | 524 | 去重处理 + 合并同题 |
| 导入 | `/import` | import.html | 392 | Excel/Word 导入 |
| AI 批量出题 | `/ai-generate` | ai-generate.html | 175 | AI 自动生成题目 |
| 考试资料 | `/syllabus` | syllabus.html | 204 | 考试大纲 + 教材内容 |
| 导出评分脚本 | `/export-rubrics` | export-rubrics.html | ~135 | 批量导出评分脚本 |
| 一致检查 | `/consistency-check` | consistency-check.html | ~158 | 批量一致检查 |

所有页面均为 Vue 3 + Element Plus 独立应用，通过 `send_file` 返回静态 HTML（避免 Jinja2 与 Vue `{{ }}` 冲突）。

**`/management` 核心功能：**

1. **题目列表** — 科目筛选、关键词搜索、质量筛选、分页（20/页）、查看/编辑/评分/删除
2. **题库总览** — 统计卡片、覆盖率、质量分布、最近评分趋势
3. **英语编辑器** — 5 步工作流（通过 `window.EnglishEditCore` 模块化）

### 6.2 聚焦评分（dist/index.html）

暗色主题 Vanilla JS + Tailwind CSS，约 630 行。

**侧边栏：**
- 单题评分（核心功能）
- 历史记录
- 批量测试/规则验证/自动调优（标记为暂未开放）
- 评分配置

**单题评分流程：**
1. 从题库下拉选择题目（或手动输入）
2. 加载题目信息卡片（标题、内容、标准答案、评分脚本、满分）
3. 输入学生答案
4. 点击「开始评分」→ POST /api/grade
5. 展示评分结果（分数、置信度、预警、评语、详情）
6. 可「保存为测试用例」→ POST /api/questions/<id>/test-cases

---

## 7. 完整工作流程

```
题目创建 → 评分脚本生成 → 测试用例添加 → 验证迭代 → 投入评分
    │              │              │             │           │
    ▼              ▼              ▼             ▼           ▼
  手动/AI       AI生成脚本    模拟+真实答案   100%通过率    单题评分
  导入题目      结构化指令    持久化存储      迭代改进脚本  批量评分
```

1. **创建题目**：手动输入或粘贴原始文本自动拆分
2. **生成评分脚本**：AI 根据题干+答案+评分规则生成结构化脚本
3. **添加测试用例**：模拟考生作答 + 真实考生作答，标注期望分数
4. **验证评分脚本**：所有测试用例过评分引擎，对比实际分 vs 期望分，在容差内即通过
5. **迭代改进**：未通过则修改脚本重新验证，直到 100% 通过
6. **投入评分**：学生作答 → 评分引擎 + 已验证的脚本 → 给出分数

---

## 8. 启动方式

```bash
cd /Users/peikingdog/allexam.sys/question-bank/ai-grading-system
python main.py
```

访问：
- 题库管理：http://localhost:5005/management
- 聚焦评分：http://localhost:5005/grading

### 备份恢复

```bash
cd /Users/peikingdog/allexam.sys/question-bank
tar xzf ai-grading-system-backup-YYYYMMDD_HHMMSS.tar.gz
```

---

## 9. 待解决问题

### 技术债

1. **遗留代码清理** — `routes.py`、`batch_routes.py`、`validation_routes.py`、`tuning_routes.py`、`engine.py`、`auto_tuning.py`、`validation.py`、`test_data.py` 以及 `app/models/` 下的多模型客户端均未被实际使用，可清理
2. **async 伪装** — `api_routes.py` 中 `grade_answer`、`create_batch`、`verify_rubric` 标记为 `async def`，但使用同步 OpenAI 客户端，实际会阻塞
3. **端口不一致** — `main.py`(5005)、`start.sh`(5000)、`settings.py`(5001) 三处不一致
4. **rubrics 表未使用** — 已定义但无任何路由引用
5. **static/ 目录未使用** — 两个前端均不依赖此目录
6. **templates/index.html** — 旧版遗留，已被 question-bank.html 替代

### 功能缺口

1. **批量评分/规则验证/自动调优** — 前端标记为"暂未开放"，后端路由存在但依赖遗留的多模型引擎
2. **无权限控制** — 所有 API 暴露，无认证
3. **无输入验证** — API 层缺少参数校验和类型检查
4. **无单元测试** — tests/ 目录为空

### 改进方向

1. 多模型评分切换 — 当前仅用 Qwen，可启用 GLM/ERNIE 做交叉验证
2. 评分脚本模板库 — 按题型（简答/论述/计算）建立通用模板
3. 批量导入/导出 — 题目和测试用例的 JSON/CSV 导入导出
4. 评分报告 — 按科目/考试生成评分统计报告
