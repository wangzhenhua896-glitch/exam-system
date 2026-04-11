# AI 智能评分系统 — CLAUDE.md

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
├── api_routes.py       # ★ 主 API（评分/题目/历史/批量/脚本生成/敏感词/用户）
├── routes.py           # 聚合评分引擎路由（历史遗留，新入口走 api_routes）
├── config_routes.py    # 模型配置管理 API
├── qwen_engine.py      # ★ 核心评分引擎 QwenGradingEngine
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
static/js/              # 前端模块：api.js + useXxx.js（组合式）
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
POST /api/batch  →  { "task_name": "...", "answers": [{"question":"..","answer":"..","max_score":8},...] }
GET  /api/batch/{task_id}  →  查询进度和结果
```

### 其他关键 API
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate-rubric-script` | AI 生成评分脚本 |
| POST | `/api/verify-rubric` | 用测试用例验证评分脚本准确性 |
| POST | `/api/evaluate-question` | AI 命题质量评估 |
| POST | `/api/auto-generate` | AI 自动出题+脚本+测试用例 |
| POST | `/api/questions/{id}/generate-test-cases` | 为已有题目生成测试用例 |
| GET  | `/api/providers` | 列出可用模型及子模型 |
| GET  | `/api/stats` | 统计信息 |
| GET  | `/api/dashboard` | 题库总览仪表盘 |

## 评分流程（v2.1.0 10步流水线）
1. 空答案预检（正则去标点后 <2字 → 直接0分）
2. 敏感词扫描（high 级别 → 直接0分）
3. 反作弊检测（复制题干/空白/答非所问 → 0分）
4. 构造 scoring_items
5. LLM 评分（按科目走不同提示词）
6. 结果解析（JSON 提取 + 正则兜底 + 3次重试）
7. 语义校验（text2vec 向量相似度 ≥0.72 → 自动纠偏，英语跳过）
8. 证据验证（quoted_text 是否真实存在于答案中）
9. 判别 Agent（短答案高分检测 / 全满分检测）
10. 边界检查 + 一致性检查（同学生同题差异 >20% → 标记）

## 关键设计原则
- **一致性 P0**: 同一答案多次评分必须同分
- **科目分支**: 思政/语文/英语各有独立提示词和输出解析格式
- **总分由系统累加**: 不信任模型给出的总分，从 scoring_items 逐项累加
- **不静默返回0分**: API/解析失败必重试3次，耗尽返回 score=null
- **配置分层**: .env → Python 默认 → 数据库覆盖（DB 优先）
- **前端非构建**: Vue 3 CDN 引入，原生 JS 组合式 API（useXxx.js）
- **数据库无 ORM**: 直接 sqlite3 操作，ALTER TABLE 兼容旧库

## 数据库（9 张表）
questions / grading_records / test_cases / model_configs /
rubric_script_history / syllabus / batch_tasks / users / sensitive_words

直接 sqlite3 操作。DB 路径: `data/exam_system.db`

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

### 远程部署
```bash
./deploy.sh                    # 部署到默认服务器 (123.56.117.123)
./deploy.sh 192.168.1.100      # 部署到指定服务器
```
部署流程：tar 打包传输 → pip 安装依赖 → 停止旧进程 → nohup 启动 → 健康检查

### 日志
- 应用日志: `app.log`（nohup 输出）
- loguru 日志: `logs/grading_{time}.log`（按天轮转，保留7天）

### 页面路由
| 路径 | 功能 |
|------|------|
| `/login` | 登录页 |
| `/management` | 题库管理（科目、题目、评分脚本） |
| `/grading` | 单题评分 |
| `/test-cases` | 测试集管理 |
| `/sensitive-words` | 敏感词管理 |
| `/user-management` | 用户管理 |

## 文档索引
| 文档 | 说明 |
|------|------|
| docs/AI智能评分系统设计文档-v2.0.0.md | ★ 最权威参考（1327行） |
| docs/PROJECT_SUMMARY.md | 架构/目录/数据库/API 总览 |
| docs/双Agent评分系统重构方案-v1.0.0.md | 双 Agent 流水线方案 |
| docs/语义校验测试用例说明.md | text2vec 语义校验模块 |
| docs/评分一致性测试报告-20260410.md | 8模型×8版本一致性测试 |
| docs/多模型配置系统设计.md | Provider→Model→Instance 三层管理 |
| docs/评分脚本版本管理.md | 自动归档/独立版本/回滚 |
| docs/TEST_CASES_MODULE.md | 测试集管理模块 |
