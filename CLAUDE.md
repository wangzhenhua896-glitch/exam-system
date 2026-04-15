# AI 智能评分系统 — CLAUDE.md

## 多 Agent 协作规则（必读）

本项目有多个 Agent 在不同电脑上同时工作，还有一台测试电脑。**每次开始工作前必须执行以下步骤：**

1. `git pull` 拉取最新代码
2. 查看 `WORKING.md`，了解其他 Agent 正在改哪些文件
3. 把自己要改的文件写进 `WORKING.md` 的"正在进行"栏，然后 `git push`
4. 完成后把自己的记录从"正在进行"删掉，再 `git push`

**文件归属（避免冲突）：**
- 英语相关文件（`english_prompts.py`、`englishEdit{Helpers,AI,ValidateSave,Core}.js`、`/english/` 接口）→ 英语 Agent 负责
- 后端其余文件（`api_routes.py` 非英语部分、`db_models.py` 等）→ 后端 Agent 负责
- `templates/question-bank.html` → 改之前先协商

**语言要求：和王老师沟通全程用中文，解释要简单易懂。**

## 产品定位
基于大语言模型的**主观题（简答题）自动评分引擎**。
可通过 API 对外提供评分服务，供第三方考试/教务系统集成调用。
同时自带管理后台用于题库维护、测试验证、模型配置。

## 技术栈
- 后端: Flask 3.0.2 / SQLite / asyncio / pydantic / loguru
- 前端: Vue 3 (CDN) + Element Plus + Axios，**非 npm 构建**
- 模型: OpenAI 兼容接口统一调用（通义/豆包/GLM/文心/MiniMax/小米/讯飞）
- 启动: `python main.py` → http://localhost:5001

## 目录结构
```
app/
├── app.py              # Flask 工厂 + 路由注册
├── api_routes.py       # ★ 主 API（评分/题目/历史/批量/脚本生成/敏感词/用户/英语编辑器AI接口）
├── routes.py           # 聚合评分引擎路由（历史遗留，新入口走 api_routes）
├── config_routes.py    # 模型配置管理 API
├── qwen_engine.py      # ★ 核心评分引擎 QwenGradingEngine
├── english_grader.py   # ★ 英语采分点精确匹配引擎（812行）
├── english_prompts.py  # 英语科目 Prompt（含编辑器 AI 接口提示词）
├── three_layer_grader.py # 三层并行评分调度
├── semantic_checker.py # 语义校验（text2vec 向量相似度纠偏）
├── validation.py       # 验证引擎
├── engine.py           # 多模型聚合引擎（历史遗留）
├── models/
│   ├── db_models.py    # SQLite 原始操作（无 ORM，ALTER TABLE 兼容旧库）
│   └── registry.py     # 模型注册表
config/
├── settings.py         # 默认配置 + .env 加载
templates/              # Jinja2 页面（login/question-bank/test-cases/sensitive-words/user-management）
dist/index.html         # 单题评分页（Vue 3 SPA）
static/js/              # 前端模块：api.js + useXxx.js（组合式）+ englishEdit{Helpers,AI,ValidateSave,Core}.js
data/exam_system.db     # SQLite 数据库
docs/                   # 设计文档
exports/                # 评分脚本导出示例
```

## 核心 API（对外评分接口）

### 单题评分
```
POST /api/grade
{
  "question_id": 5,          # 可选，传了则从 DB 加载题目+评分脚本
  "answer": "学生答案文本",
  "question": "题目内容",    # question_id 为空时必填
  "max_score": 8,            # 默认 10
  "subject": "politics",     # politics/chinese/english/general
  "rubric": {...},           # 可选，自定义评分标准
  "provider": "doubao",      # 可选，指定模型服务商
  "model": "deepseek-v3",   # 可选，指定子模型
  "student_id": "001",       # 可选，用于一致性校验
  "student_name": "张三",    # 可选
  "exam_name": "期中考试"     # 可选
}
→ {
  "success": true,
  "data": {
    "record_id": 123,
    "score": 6.0,
    "confidence": 0.85,
    "comment": "评语...",
    "details": { "scoring_items": [...], "final_score": 6.0, ... },
    "model_used": "qwen-agent",
    "needs_review": false,
    "warning": null,
    "grading_flags": []
  }
}
```

### 批量评分
```
POST /api/batch  →  { "task_name": "...", "answers": [{"question_id": 5, "answer":"..", "max_score":8},...] }
GET  /api/batch/{task_id}  →  查询进度和结果
```
注意：批量评分通过 question_id 从 DB 自动获取 subject，也可在 item 中直接传 subject。

### 其他关键 API
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate-rubric-script` | AI 生成评分脚本（传 subject 切换中/英文提示词） |
| POST | `/api/verify-rubric` | 用测试用例验证评分脚本准确性（自动获取 subject） |
| POST | `/api/evaluate-question` | AI 命题质量评估（传 subject 切换中/英文标准） |
| POST | `/api/auto-generate` | AI 自动出题+脚本+测试用例（传 subject 切换语言） |
| POST | `/api/questions/{id}/generate-test-cases` | 为已有题目生成测试用例（自动获取 subject，风格选项随科目动态） |
| GET  | `/api/providers` | 列出可用模型及子模型 |
| GET  | `/api/stats` | 统计信息 |
| GET  | `/api/dashboard` | 题库总览仪表盘 |
| GET  | `/api/questions/{id}/answers` | 获取满分答案列表 |
| POST | `/api/questions/{id}/answers` | 添加满分答案 |
| PUT  | `/api/questions/{id}/answers/{aid}` | 修改满分答案 |
| DELETE | `/api/questions/{id}/answers/{aid}` | 删除满分答案 |
| GET  | `/api/grading-params` | 获取评分参数配置 |
| PUT  | `/api/grading-params/{key}` | 修改评分参数 |
| GET  | `/api/questions/{id}/children` | 获取子题列表 |
| GET  | `/api/questions/{id}/with-children` | 获取题目含子题 |
| PUT  | `/api/questions/{id}/workflow-status` | 轻量更新工作流状态（不触发脚本快照） |
| POST | `/api/english/extract` | AI 提取子题+采分点（英语编辑器用） |
| POST | `/api/english/suggest-synonyms` | AI 同义词补全 |
| POST | `/api/english/suggest-exclude` | AI 排除词建议 |
| POST | `/api/english/generate-rubric` | AI 生成评分脚本（编辑器用） |

## 评分流程（v3.0.0 三层并行 + 策略取分）
1. 空答案预检（正则去标点后 <2字 → 直接0分；英语按词数 <2词判断）
2. 敏感词扫描（high 级别 → 直接0分）
3. **三层并行执行**：
   - 第1层：关键词匹配（英语采分点逐个检查）→ 得分_A
   - 第2层：向量匹配度（text2vec 相似度 × 满分）→ 得分_B（**英语跳过**：中文 text2vec 对英文不可靠）
   - 第3层：LLM 评分（按科目走不同提示词）→ 得分_C
4. 按策略取最终得分（max / min / avg / median）
5. 证据验证（quoted_text 是否真实存在于答案中）
6. 判别 Agent（短答案高分检测：中文按字数<10，英语按词数<5 / 全满分检测）
7. 边界检查 + 一致性检查（同学生同题差异 >20% → 标记）

**策略配置**：全局默认存在 grading_params 表，单题可在 questions.scoring_strategy 覆盖

## 关键设计原则
- **一致性 P0**: 同一答案多次评分必须同分
- **科目分支**: 思政/语文/英语各有独立提示词和输出解析格式，所有涉及评分/生成的 API 均需传 subject
- **英语跳过向量层**: 中文 text2vec 对英文不可靠，英语科目不执行向量匹配
- **总分由系统累加**: 不信任模型给出的总分，从 scoring_items 逐项累加
- **不静默返回0分**: API/解析失败必重试3次，耗尽返回 score=null
- **配置分层**: .env → Python 默认 → 数据库覆盖（DB 优先）
- **前端非构建**: Vue 3 CDN 引入，原生 JS 组合式 API（useXxx.js）；题型编辑器用全局变量暴露（englishEditCore.js → window.EnglishEditCore，子模块拆为 helpers/AI/validateSave 三个 IIFE）
- **数据库无 ORM**: 直接 sqlite3 操作，ALTER TABLE 兼容旧库
- **题型抽象**: 前端 EDITOR_REGISTRY 按 question_type 路由编辑器；后端按 rubric.type 分流评分函数；DB 通过 question_type + scope_type + answer_text 格式适配，不新建表
- **编辑器产出 = 引擎输入**: buildApiPayload() 输出的 JSON 就是 english_scoring_point_match() 直接消费的格式，中间不做转换

## 数据库（12 张表）
questions / grading_records / test_cases / model_configs /
rubric_script_history / syllabus / batch_tasks / users / sensitive_words /
question_answers / grading_params / rubrics / bug_log

直接 sqlite3 操作。DB 路径: `data/exam_system.db`

### questions 表关键列
- `question_type` — 题型标识（essay/single_choice/multi_choice/fill_blank/true_false/translation），默认 essay
- `workflow_status` — 工作流状态 JSON（独立列，不存 rubric 中避免覆盖）
- `parent_id` — 父题关系，NULL 为父题，非 NULL 为子题
- `scoring_strategy` — 单题评分策略覆盖（max/min/avg/median），NULL 使用全局默认
- `rubric` — JSON 格式，新格式含 `type` + `version` 字段

### 英语编辑器前端模块
- `static/js/englishEditCore.js` — 5 步工作流状态机（编排层），通过 `window.EnglishEditCore` 全局暴露；子模块：`englishEditHelpers.js`（纯工具）、`englishEditAI.js`（AI API）、`englishEditValidateSave.js`（验证+保存）
- 非 ES Module 模式（question-bank.html 用 `<script>` 引入）
- 核心函数：`useEnglishEdit()` 返回响应式状态和方法集合
- `buildApiPayload()` 生成的 JSON 必须与评分引擎 `english_scoring_point_match()` 消费格式完全一致

## 评分脚本编写规范

评分脚本是评分的**唯一依据**，阅卷模型只看到脚本和学生答案。必须做到：

### 结构（按顺序）
1. 【题目信息】— 完整复述题目和满分值
2. 【标准答案要点】— 每个要点含核心含义 + 关键词 + 等价表述
3. 【逐项评分规则】— 每个得分点的得分/部分得分/不得分/易混淆判断
4. 【反作弊规则】— 复制题干、空白、答非所问等判0分条件
5. 【作答情况分类】— 完整/部分/空白/口语化等典型模式的评分方式
6. 【扣分规则】— 错别字扣分等（无则写"无额外扣分项"）
7. 【总分计算】— 总分 = 各项之和 - 扣分，范围 [0, 满分]
8. 【输出格式要求】— 强制 JSON 格式

### 语言要求
- **禁止**："酌情给分"、"视情况"、"适当给分"、"根据质量"
- **必须**："如果...则得X分"、"只要提到...即得X分"、"未提到...则0分"
- 每个得分点分值明确，不能有范围值

### 一致性保障
- 每个得分点用【必含关键词】+【等价表述】双重判断
- 关键词匹配优先于语义匹配
- 明确区分"必须同时满足"和"满足其一即可"

## 环境变量与安全

### .env 配置（从 .env.example 复制）
- `.env` 已在 `.gitignore` 中，**不会被提交**
- `deploy.sh` 也已加入 `.gitignore`（含服务器密码）
- 部署时只同步 `.env.example`，远程需手动创建 `.env`

### 敏感信息清单
- `.env` — 各服务商 API Key
- `deploy.sh` — 远程服务器密码（已 gitignore）
- `app.py` SECRET_KEY — 生产环境应改为随机值
- `data/exam_system.db` — 已 gitignore

### 模型配置优先级
1. 数据库 `model_configs` 表（管理员通过 Web UI 修改）— **最高优先级**
2. `.env` 环境变量
3. `config/settings.py` 硬编码默认值

## 部署与运维

### 本地开发
```bash
cp .env.example .env          # 编辑填入 API Key
pip install -r requirements.txt
python main.py                 # → http://localhost:5001
```

### 服务管理
```bash
./start.sh start               # 启动
./start.sh stop                # 停止
./start.sh restart             # 重启
./start.sh status              # 查看状态
```

### 阿里云服务器

- **IP**: 123.56.117.123
- **用户**: root
- **远程目录**: `/opt/ai-grading`
- **默认端口**: 5001
- **Python**: `/usr/bin/python3.11`
- **数据库**: 服务器上独立维护，不会被本地覆盖（deploy.sh 排除了 `data/`）

### 远程部署
```bash
./deploy.sh                          # 部署到默认服务器 5001 端口
./deploy.sh 123.56.117.123 -p 5002   # 指定端口（多版本并行）
./deploy.sh 123.56.117.123 -d /opt/ai-grading-v2  # 指定目录
./deploy.sh 123.56.117.123 -p 5002 -d /opt/ai-grading-v2  # 全指定
```
部署流程：tar 打包传输（排除 data/exports/logs/.env）→ pip 安装依赖 → 停止旧进程（按端口定位）→ nohup 启动 → 健康检查

远程日志查看：
```bash
ssh root@123.56.117.123 'tail -30 /opt/ai-grading/app-5001.log'
```

### 日志
- 应用日志: `app.log`（nohup 输出）
- loguru 日志: `logs/grading_{time}.log`（按天轮转，保留7天）

### 页面路由
| 路径 | 功能 |
|------|------|
| `/login` | 登录页 |
| `/management` | 题库管理（题目列表、评分脚本、英语专用编辑器），科目在登录时选定，页内不再重复选择 |
| `/question-edit` | 题目编辑/新建/查看 |
| `/dedup` | 去重合并 |
| `/import` | 导入题目 |
| `/ai-generate` | AI 批量出题 |
| `/syllabus` | 考试大纲/教材 |
| `/export-rubrics` | 导出评分脚本 |
| `/consistency-check` | 一致检查 |
| `/grading` | 单题评分 |
| `/test-cases` | 测试集管理 |
| `/sensitive-words` | 敏感词管理 |
| `/user-management` | 用户管理 |

## 文档索引
| 文档 | 说明 |
|------|------|
| docs/数据字典.md | ★ 数据库 12 张表的字段/类型/约束/关系 |
| docs/AI智能评分系统设计文档-v2.0.0.md | ★ 最权威参考（1327行） |
| docs/PROJECT_SUMMARY.md | 架构/目录/数据库/API 总览 |
| docs/多满分答案设计方案.md | ★ 多满分答案+父子题+三层并行评分方案 |
| docs/英语采分点评分方案.md | ★ 英语采分点精确匹配+LLM 兜底方案 |
| docs/英语评分模块独立设计.md | 英语评分模块架构设计 |
| docs/英语简答题文档拆分方案.md | 英语题目 Word 文档解析拆分 |
| docs/英语LLM兜底方案设计.md | 英语 LLM 评分兜底策略 |
| docs/双Agent评分系统重构方案-v1.0.0.md | 双 Agent 流水线方案 |
| docs/多模型配置系统设计.md | Provider→Model→Instance 三层管理 |
| docs/评分脚本版本管理.md | 自动归档/独立版本/回滚 |
| docs/评分脚本自查自纠方案.md | 四层检查体系（结构/对齐/验证/一致性） |
| docs/语义校验测试用例说明.md | text2vec 语义校验模块 |
| docs/TEST_CASES_MODULE.md | 测试集管理模块 |
| docs/前端代码审查与改进清单.md | ★ 前端代码审查（P0×5/P1×13/P2×10 + 架构问题） |
| docs/页面设计规范.md | 前端页面设计规范与交互约定 |
| docs/待办工作清单.md | 待办事项跟踪 |
| docs/Gitea本地备份配置.md | Gitea 本地 Git 备份配置 |
| docs/MODEL_CONFIG.md | 模型配置管理说明 |
| docs/测试技巧与自动化指南.md | Playwright + API 测试方法手册、常见坑 |
| docs/英语采分点评分验证报告-20260415.md | ★ 0007-0012 采分点评分验证（34用例，含1个Bug记录） |
| docs/api_routes拆分方案.md | ★ api_routes.py 拆分为11个文件的详细方案（后端Agent执行用） |
| docs/archive/ | 已归档的过程记录（Bug修复/优化/测试报告等） |
