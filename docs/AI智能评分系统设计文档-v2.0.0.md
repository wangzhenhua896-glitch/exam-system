# AI 智能评分系统设计文档

> **文档版本**: v2.2.0
> **最后更新**: 2026-04-10
> **维护者**: AI Grading System Team

---

## 目录

1. [系统概述](#1-系统概述)
2. [技术架构](#2-技术架构)
3. [项目结构](#3-项目结构)
4. [核心模块设计](#4-核心模块设计)
5. [数据库设计](#5-数据库设计)
6. [API 接口设计](#6-api-接口设计)
7. [前端架构](#7-前端架构)
8. [核心业务流程](#8-核心业务流程)
9. [核心算法设计](#9-核心算法设计)
10. [配置系统](#10-配置系统)
11. [评分一致性保障体系](#11-评分一致性保障体系)
12. [科目专用评分流程](#12-科目专用评分流程)
13. [部署与运维](#13-部署与运维)
14. [扩展指南](#14-扩展指南)
15. [版本历史](#15-版本历史)
16. [附录](#16-附录)

---

## 1. 系统概述

### 1.1 系统定位

AI 智能评分系统是一个基于国产大模型的**简答题自动评分平台**，支持多模型并行评分、聚合策略、评分验证与自动调优等功能。

### 1.2 核心功能

| 功能模块 | 说明 |
|---------|------|
| **多模型评分** | 支持通义千问、智谱 GLM、MiniMax、百度文心、字节豆包等 5+ 国产大模型 |
| **聚合策略** | 多数投票、加权平均、置信度加权三种聚合策略 |
| **评分验证** | 基于测试数据集验证评分准确性、计算 Pearson 相关系数 |
| **自动调优** | 迭代优化温度参数和提示词模板，提升评分准确率 |
| **批量评分** | 支持批量题目评分和性能测试 |
| **题库管理** | 题目 CRUD、评分标准配置、评分脚本管理 |
| **角色权限** | 管理员（系统配置）+ 科目老师（评分业务） |
| **用户管理** | 用户 CRUD、登录身份选择、科目绑定 |
| **一致性保障** | student_id 追踪、同题多次评分一致性校验、判别 Agent |
| **科目专用评分** | 思政/语文/英语各自独立的提示词和输出解析流程 |

### 1.3 设计原则

- **多模型解耦**: 统一 `BaseModelClient` 接口，新增模型只需实现子类
- **配置分层**: `.env` 默认 → Python 配置 → 数据库覆盖，灵活可配
- **异步并发**: 全链路异步设计，支持高并发评分
- **可验证性**: 内置验证引擎和测试数据集，确保评分质量
- **可观测性**: 完整日志记录、评分历史、统计监控
- **一致性优先**: 同一答案多次评分必须给出相同分数（P0 原则）

---

## 2. 技术架构

### 2.1 技术栈

#### 后端

| 组件 | 技术 | 版本 |
|------|------|------|
| Web 框架 | Flask | 3.0.2 |
| 异步运行时 | asyncio + aiohttp | - |
| 数据库 | SQLite 3 | - |
| 数据验证 | pydantic | 2.6.3 |
| 数据处理 | numpy, pandas | 1.26.4 / 2.2.1 |
| 日志 | loguru | 0.7.2 |

#### 大模型 SDK

| 服务商 | SDK | 调用方式 |
|--------|-----|---------|
| 通义千问、豆包 | openai (AsyncOpenAI) | 异步直接调用 |
| 智谱 GLM | zhipuai 2.0.1 | run_in_executor 同步转异步 |
| 百度文心 | qianfan 0.3.0 | run_in_executor 同步转异步 |
| MiniMax | httpx | HTTP POST 直接调用 |

#### 前端

| 组件 | 技术 |
|------|------|
| 框架 | Vue 3 (vue.global.prod.js) |
| UI 库 | Element Plus |
| HTTP 客户端 | Axios |
| 其他 | 原生 JavaScript (static/js/app.js) |

### 2.2 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                      表现层 (Presentation)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  登录页面     │  │  题库管理     │  │  评分页面     │  │
│  │  login.html  │  │  question-   │  │  dist/index  │  │
│  │              │  │  bank.html   │  │  .html       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  敏感词管理   │  │  用户管理     │  │  测试集管理   │  │
│  │  sensitive-  │  │  user-       │  │  test-       │  │
│  │  words.html  │  │  management  │  │  cases.html  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      路由层 (Routing)                     │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │grading_bp  │ │batch_bp  │ │valid_bp  │ │tuning_bp │ │
│  │/api/grading│ │/api/batch│ │/api/valid│ │/api/tune │ │
│  └────────────┘ └──────────┘ └──────────┘ └──────────┘ │
│  ┌────────────┐ ┌──────────┐                            │
│  │api_bp      │ │config_bp │                            │
│  │/api        │ │/api/conf │                            │
│  └────────────┘ └──────────┘                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    业务逻辑层 (Business)                   │
│  ┌────────────────────┐  ┌────────────────────┐        │
│  │  QwenGradingEngine │  │  AggregationEngine │        │
│  │  (主评分引擎)       │  │  (聚合引擎)         │        │
│  │  - 科目分支路由     │  │                    │        │
│  │  - 思政专用提示词   │  │                    │        │
│  │  - 判别Agent       │  │                    │        │
│  │  - 一致性校验       │  │                    │        │
│  └────────────────────┘  └────────────────────┘        │
│  ┌────────────────────┐  ┌────────────────────┐        │
│  │  ValidationEngine  │  │  AutoTuningEngine  │        │
│  │  (验证引擎)         │  │  (调优引擎)         │        │
│  └────────────────────┘  └────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    模型客户端层 (Models)                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  │qwen  │ │glm   │ │minimax│ │ernie │ │doubao│          │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘          │
│              ModelRegistry (单例注册表)                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    数据访问层 (Data)                       │
│              SQLite + 原生 SQL (db_models.py)             │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 项目结构

```
ai-grading-system/
├── main.py                      # 主入口：Flask 应用启动
├── start.sh                     # 启动脚本：环境检查 + 依赖安装
├── auto_generate.py             # AI 自动出题 + 测试用例生成器
├── requirements.txt             # Python 依赖清单
├── .env.example                 # 环境变量模板
├── README.md                    # 项目文档
│
├── app/                         # 核心应用模块
│   ├── app.py                   # Flask 应用工厂 + 路由注册
│   ├── routes.py                # 评分 API（单题评分、模型/策略列表）
│   ├── api_routes.py            # 数据库 API 路由（题目 CRUD、评分、批量、统计）
│   ├── batch_routes.py          # 批量评分 API
│   ├── validation_routes.py     # 评分规则验证 API
│   ├── tuning_routes.py         # 自动调优 API
│   ├── config_routes.py         # 模型配置管理 API
│   ├── engine.py                # 多模型聚合引擎（三种聚合策略）
│   ├── qwen_engine.py           # 主评分引擎（Qwen-Agent 风格）
│   ├── validation.py            # 验证引擎
│   ├── auto_tuning.py           # 自动调优引擎
│   ├── semantic_checker.py      # 语义相似度校验
│   ├── test_data.py             # 内置测试数据集
│   └── models/                  # 模型客户端层
│       ├── base.py              # 抽象基类 + 枚举 + 响应模型
│       ├── registry.py          # 模型注册表（单例模式）
│       ├── qwen.py              # 通义千问客户端
│       ├── glm.py               # 智谱 GLM 客户端
│       ├── minimax.py           # MiniMax 客户端
│       ├── ernie.py             # 百度文心客户端
│       └── doubao.py            # 字节豆包客户端
│
├── config/
│   └── settings.py              # 全局配置（模型、评分、Web、数据库）
│
├── data/                        # 数据目录
│   └── exam_system.db           # SQLite 数据库
│
├── templates/                   # 前端 HTML 页面
│   ├── login.html               # 登录页（用户选择 + 角色选择）
│   ├── question-bank.html       # 题库管理（Vue 3 + Element Plus）
│   ├── test-cases.html          # 测试用例管理页
│   ├── sensitive-words.html     # 敏感词管理页
│   └── user-management.html     # 用户管理页（管理员专用）
│
├── static/                      # 静态资源
│   ├── css/style.css
│   ├── js/app.js                # 原生 JS 前端逻辑
│   ├── vendor/                  # 第三方库（Vue、Element Plus、Axios）
│   ├── index.html               # dist 备用
│   └── code-viewer.html         # 评分引擎源码查看器
│
├── dist/                        # 单题评分页（Vue 构建产物）
├── logs/                        # 日志目录（loguru 轮转）
├── docs/                        # 文档目录
└── tests/                       # 测试目录
```

---

## 4. 核心模块设计

### 4.1 Flask 应用工厂 (`app/app.py`)

**职责**: 创建 Flask 实例、注册路由、配置错误处理

**关键函数**:

```python
def create_app():
    """应用工厂函数"""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config['SECRET_KEY'] = 'your-secret-key'

    # 启用 CORS
    CORS(app)

    # 注册路由
    register_routes(app)

    # 注册错误处理
    register_error_handlers(app)

    return app
```

**路由注册**:

| Blueprint | URL 前缀 | 文件 | 职责 |
|-----------|----------|------|------|
| `grading_bp` | `/api/grading` | `routes.py` | 单题评分、模型/策略列表 |
| `batch_bp` | `/api/batch` | `batch_routes.py` | 批量评分、性能测试 |
| `validation_bp` | `/api/validation` | `validation_routes.py` | 评分验证 |
| `tuning_bp` | `/api/tuning` | `tuning_routes.py` | 自动调优 |
| `api_bp` | `/api` | `api_routes.py` | 题目 CRUD、评分、统计、用户、敏感词 |
| `config_bp` | `/api/config` | `config_routes.py` | 模型配置管理 |

**页面路由**:

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | → `/login` | 根路径重定向 |
| `/login` | `login.html` | 登录页（用户选择 + 角色选择） |
| `/management` | `question-bank.html` | 题库管理（管理员/科目老师） |
| `/grading` | `dist/index.html` | 单题评分页 |
| `/test-cases` | `test-cases.html` | 测试用例管理 |
| `/sensitive-words` | `sensitive-words.html` | 敏感词管理 |
| `/user-management` | `user-management.html` | 用户管理（管理员） |
| `/code-viewer` | `code-viewer.html` | 评分引擎源码查看 |

### 4.2 主评分引擎 (`app/qwen_engine.py`)

**类**: `QwenGradingEngine`, `QwenGradingResult`

**核心方法**:

| 方法 | 职责 |
|------|------|
| `grade()` | 主入口，按科目分支路由，3 次指数退避重试（1s/2s/4s） |
| `_init_client()` | 初始化 OpenAI 兼容客户端，DB 配置 → .env 降级 |
| `set_provider()` | 运行时切换服务商和模型 |
| `_format_rubric()` | 格式化评分标准（rubricScript → rules+points 降级） |
| `_get_system_prompt()` | 通用系统提示词（角色 + 流程 + JSON + 反作弊） |
| `_get_politics_system_prompt()` | 思政专用系统提示词（严格按 rubric_script 执行） |
| `_build_user_prompt()` | 用户提示词（含 cache_buster 破缓存） |
| `_parse_output()` | 解析 LLM JSON 输出，scoring_items 累加总分 |
| `_calculate_confidence()` | 基于输出长度计算置信度 |
| `boundary_check()` | 边界检查 + 分数截断 |

**评分结果模型** (`QwenGradingResult`):

```python
class QwenGradingResult(BaseModel):
    final_score: Optional[float] = None    # 最终分数（None = 评分失败）
    confidence: float = 0                  # 置信度 0~1
    strategy: str = ""                     # 策略标识
    total_score: float = 0                 # 满分
    comment: str = ""                      # 评语
    error: Optional[str] = None            # 错误信息
    needs_review: bool = False             # 是否需要人工复核
    warning: Optional[str] = None          # 警告信息
    scoring_items: Optional[List[Dict]] = None  # 分项得分明细
```

**科目分支路由** (v2.1.0 新增):

```python
# 在 grade() 方法中
if subject == 'politics':
    system_prompt = self._get_politics_system_prompt()
else:
    system_prompt = self._get_system_prompt()
```

### 4.3 聚合引擎 (`app/engine.py`)

**类**: `AggregationEngine`, `GradingResult`

**核心方法**:

| 方法 | 职责 |
|------|------|
| `aggregate()` | 主入口，并行调用多模型多次采样 |
| `_sample_models()` | 异步并发采样（asyncio.gather） |
| `_majority_vote()` | 多数投票策略 |
| `_weighted_average()` | 简单加权平均 |
| `_confidence_weighted()` | 置信度加权（默认策略，MAD 异常过滤） |
| `_boundary_check()` | 边界检测（满分/零分/低置信度） |

**聚合策略对比**:

| 策略 | 算法 | 适用场景 |
|------|------|---------|
| **多数投票** | 分数离散化后 Counter 统计 | 评分结果波动大、需要稳定性 |
| **加权平均** | numpy mean/std | 简单场景、快速评分 |
| **置信度加权** | MAD 异常过滤 + 置信度加权 | 默认策略、高精度要求 |

### 4.4 验证引擎 (`app/validation.py`)

**类**: `ValidationEngine`

**流程**:

1. 加载测试数据集（`test_data.py`）
2. 并行评分所有测试项
3. 计算统计指标：
   - 准确率（误差 ≤ 2.0 的比例）
   - 平均误差、误差标准差、最大误差
   - Pearson 相关系数（预期 vs 实际分数）

### 4.5 自动调优引擎 (`app/auto_tuning.py`)

**类**: `AutoTuningEngine`

**迭代调优循环**（最大 10 次）:

1. 运行验证（`ValidationEngine.validate`）
2. 计算综合得分 = `accuracy * 0.6 + correlation * 0.4`
3. 检查目标：`accuracy >= 0.8 AND correlation >= 0.85`
4. 参数调整：
   - 误差 > 3.0 → 降低温度（-0.05，最低 0.1）
   - 误差 < 1.5 AND correlation > 0.9 → 提高温度（+0.02，最高 0.5）
   - 每 3 次迭代且 accuracy < 0.7 → 切换提示词模板
     - 模板序列：`default` → `detailed` → `strict` → `flexible`

### 4.6 模型客户端层 (`app/models/`)

#### 基础类 (`base.py`)

```python
class BaseModelClient(ABC):
    """基础模型客户端"""

    provider: ModelProvider
    model_name: str
    enabled: bool = True

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应（子类实现）"""
        pass

    async def grade_answer(self, question, answer, rubric, max_score):
        """评分学生答案（共用逻辑）"""
        pass

    def get_info(self) -> Dict[str, Any]:
        """获取模型信息（子类可覆盖）"""
        pass
```

**枚举**: `ModelProvider`

| 枚举值 | 说明 |
|--------|------|
| `QWEN` | 通义千问 |
| `GLM` | 智谱 GLM |
| `MINIMAX` | MiniMax |
| `ERNIE` | 百度文心 |
| `SPARK` | 讯飞星火 |
| `DOUBAO` | 字节豆包 |

#### 模型注册表 (`registry.py`)

**单例模式**，管理所有运行时模型实例

**关键方法**:

| 方法 | 说明 |
|------|------|
| `register(model)` | 注册模型实例 |
| `list_models()` | 返回所有模型信息（供前端展示） |
| `get_enabled_models()` | 返回所有启用的模型 |
| `get_model_by_provider(provider)` | 根据服务商获取模型 |
| `clear()` | 清空注册表（用于测试） |
| `init_models(config)` | 从配置初始化所有模型 |

#### 各模型客户端

| 类 | 文件 | SDK | 调用方式 |
|----|------|-----|---------|
| `QwenClient` | `qwen.py` | openai (AsyncOpenAI) | 异步直接调用 |
| `GLMClient` | `glm.py` | zhipuai (ZhipuAI) | run_in_executor 同步转异步 |
| `MiniMaxClient` | `minimax.py` | httpx (AsyncClient) | HTTP POST 直接调用 |
| `ErnieClient` | `ernie.py` | qianfan (ChatCompletion) | run_in_executor 同步转异步 |
| `DoubaoClient` | `doubao.py` | openai (AsyncOpenAI) | 异步直接调用（火山引擎 Coding Plan） |

---

## 5. 数据库设计

**数据库**: SQLite 3
**数据库文件**: `data/exam_system.db`

### 5.1 表结构

#### 5.1.1 questions (题目表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| subject | TEXT | | 科目（politics/chinese/english 等） |
| title | TEXT | | 题目标题 |
| content | TEXT | | 题目内容 |
| original_text | TEXT | | 原始文本 |
| standard_answer | TEXT | | 标准答案 |
| rubric_rules | TEXT | | 评分规则 |
| rubric_points | TEXT | | 评分要点 |
| rubric_script | TEXT | | 结构化评分脚本 |
| rubric | TEXT | NOT NULL | JSON 格式的完整评分标准 |
| max_score | REAL | | 满分 |
| quality_score | REAL | | 质量评分（AI 评估） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

#### 5.1.2 grading_records (评分记录表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| question_id | INTEGER | FK → questions.id | 关联题目 |
| student_answer | TEXT | | 学生答案 |
| student_id | TEXT | DEFAULT NULL | 学生标识（用于一致性校验） |
| score | REAL | | 得分 |
| details | TEXT | | JSON 详情 |
| model_used | TEXT | | 使用的模型 |
| confidence | REAL | | 置信度 |
| grading_flags | TEXT | DEFAULT NULL | JSON 评分标记（异常检测结果） |
| graded_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 评分时间 |

**grading_flags 字段结构**:

```json
[
  {
    "type": "fake_quote | short_answer_high_score | all_perfect | score_inconsistency | sensitive_word",
    "severity": "warning | error | info",
    "desc": "异常描述",
    "point_name": "相关评分点名称（可选）"
  }
]
```

#### 5.1.3 test_cases (测试用例表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| question_id | INTEGER | FK → questions.id | 关联题目 |
| answer_text | TEXT | | 模拟答案 |
| expected_score | REAL | | 期望分数 |
| description | TEXT | | 描述 |
| case_type | TEXT | | 类型（ai_generated/simulated/real） |
| last_actual_score | REAL | | 最近实际得分 |
| last_error | REAL | | 最近误差 |
| last_run_at | TIMESTAMP | | 最近运行时间 |

#### 5.1.4 rubric_script_history (评分脚本版本历史表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| question_id | INTEGER | FK → questions.id | 关联题目 |
| version | INTEGER | | 版本号 |
| script_text | TEXT | | 脚本内容 |
| avg_error | REAL | | 平均误差 |
| passed_count | INTEGER | | 通过用例数 |
| total_cases | INTEGER | | 总用例数 |
| note | TEXT | | 备注 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

#### 5.1.5 model_configs (模型配置表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| provider | TEXT | PK | 服务商标识（qwen/glm/doubao 等） |
| api_key | TEXT | DEFAULT '' | API 密钥 |
| base_url | TEXT | DEFAULT '' | API 地址 |
| model | TEXT | DEFAULT '' | 默认模型 |
| enabled | INTEGER | DEFAULT 0 | 是否启用（0/1） |
| extra_config | TEXT | DEFAULT '{}' | 扩展配置（JSON，含 enabled_models） |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

#### 5.1.6 users (用户表) — v2.1.0 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| username | TEXT | NOT NULL, UNIQUE | 用户名（英文） |
| display_name | TEXT | | 显示名 |
| role | TEXT | DEFAULT 'teacher' | 角色（admin/teacher） |
| subject | TEXT | DEFAULT NULL | 绑定科目 |
| is_active | INTEGER | DEFAULT 1 | 是否启用 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**预置用户**: admin（管理员）+ 9 个科目老师（politics/chinese/english/math/history/geography/physics/chemistry/biology）

#### 5.1.7 sensitive_words (敏感词表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| word | TEXT | NOT NULL | 敏感词 |
| subject | TEXT | DEFAULT 'all' | 适用科目（all = 全局） |
| category | TEXT | DEFAULT 'politics' | 分类（politics/other） |
| severity | TEXT | DEFAULT 'high' | 严重程度（high/medium/low） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

#### 5.1.8 其他表

| 表名 | 说明 |
|------|------|
| `batch_tasks` | 批量评分任务 |
| `syllabus` | 考试大纲/教材内容 |
| `rubrics` | 评分规则（备用） |
| `bug_log` | Bug 日志（评分异常记录） |

### 5.2 数据库操作模块 (`db_models.py`)

**关键函数**:

| 函数 | 说明 |
|------|------|
| `init_database()` | 初始化数据库，创建所有表 + 预置默认用户 |
| `get_db_connection()` | 获取数据库连接 |
| `get_effective_config(provider)` | 获取服务商有效配置（DB → .env 降级） |
| `add_grading_record(...)` | 添加评分记录（含 student_id, grading_flags） |
| `get_previous_grade(student_id, question_id)` | 查询同学生同题最近一次评分 |
| `get_users()` / `get_user()` | 用户查询 |
| `add_user()` / `update_user()` / `delete_user()` | 用户 CRUD |
| `get_sensitive_words(...)` | 敏感词查询（支持筛选） |
| `check_sensitive_words(answer, subject)` | 扫描答案中的敏感词 |

---

## 6. API 接口设计

### 6.1 评分 API (`/api/grading`)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/grading/single` | 单题评分（聚合引擎） |
| GET | `/api/grading/models` | 列出可用模型 |
| GET | `/api/grading/strategies` | 列出可用策略 |

### 6.2 批量 API (`/api/batch`)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/batch/grade` | 批量评分 |
| POST | `/api/batch/test` | 性能测试 |

### 6.3 核心 API (`/api`)

| 方法 | 路由 | 说明 | 请求体 |
|------|------|------|--------|
| GET | `/api/providers` | 列出已启用 provider 及子模型 | - |
| GET | `/api/questions` | 获取题目列表 | `?subject=xxx` |
| GET | `/api/questions/:id` | 获取题目详情 | - |
| POST | `/api/questions` | 创建题目 | `{subject, title, content, ...}` |
| PUT | `/api/questions/:id` | 更新题目 | 同创建 |
| DELETE | `/api/questions/:id` | 删除题目 | - |
| **POST** | **`/api/grade`** | **评分答案** | **`{question_id, answer, student_id, provider, model}`** |
| GET | `/api/history` | 获取评分历史 | `?question_id=xxx` |
| GET | `/api/stats` | 获取统计信息 | - |
| GET | `/api/dashboard` | 题库总览 | `?subject=xxx` |
| GET | `/api/export-rubric-scripts` | 导出评分脚本 | `?subject=xxx` |
| GET | `/api/models/available` | 获取所有可用模型 | - |
| POST | `/api/generate-rubric-script` | AI 生成评分脚本（传 subject 切换中/英文） | `{content, score, standardAnswer, subject}` |
| POST | `/api/evaluate-question` | AI 命题质量评估（传 subject 切换标准） | `{content, standardAnswer, subject}` |
| POST | `/api/verify-rubric` | 验证评分脚本（自动获取 subject） | `{question_id, tolerance}` |
| POST | `/api/auto-generate` | AI 自动出题（传 subject 切换语言） | `{subject, count, testcase_count}` |
| POST | `/api/generate-answer` | 生成模拟答案 | `{question_id}` |
| GET | `/api/bugs` | 获取 bug 日志 | `?bug_type=xxx` |

#### 6.3.1 POST /api/grade 请求/响应

**请求体**:

```json
{
  "question_id": 5,
  "answer": "学生答案文本",
  "student_id": "politics",
  "provider": "qwen",
  "model": "qwen-plus"
}
```

**响应** (v2.1.0):

```json
{
  "success": true,
  "data": {
    "record_id": 123,
    "score": 7.5,
    "confidence": 0.85,
    "comment": "要点1命中...要点2部分命中...",
    "details": { "final_score": 7.5, "scoring_items": [...], "..." },
    "model_used": "qwen-agent",
    "needs_review": false,
    "warning": null,
    "grading_flags": [
      {
        "type": "score_inconsistency",
        "severity": "warning",
        "desc": "与上次评分(8分)差异较大(0.5分)，可能评分不一致"
      }
    ]
  }
}
```

**评分流程（v2.1.0 完整流程）**:

```
1. 空答案预检 → len(stripped) < 2 → 0分（不调LLM）
2. 敏感词扫描 → high 命中 → 0分（不调LLM）
3. LLM 评分（科目分支） → 3次重试
4. 证据真实性验证（quoted_text 是否存在于原文）
5. 判别Agent：短答案高分检测
6. 判别Agent：全满分检测
7. 保存评分记录（含 student_id）
8. 一致性校验（同学生同题历史对比）
9. 返回结果
```

#### 6.3.2 用户管理 API (v2.1.0 新增)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/users` | 获取用户列表 |
| POST | `/api/users` | 新增用户 |
| PUT | `/api/users/:id` | 更新用户 |
| DELETE | `/api/users/:id` | 删除用户 |

#### 6.3.3 敏感词 API

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/sensitive-words` | 获取敏感词列表（支持筛选） |
| POST | `/api/sensitive-words` | 添加敏感词 |
| PUT | `/api/sensitive-words/:id` | 更新敏感词 |
| DELETE | `/api/sensitive-words/:id` | 删除敏感词 |
| POST | `/api/sensitive-words/batch` | 批量导入敏感词 |

### 6.4 验证 API (`/api/validation`)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/validation/run` | 运行评分规则验证 |
| GET | `/api/validation/dataset` | 获取测试数据集信息 |

### 6.5 调优 API (`/api/tuning`)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/tuning/start` | 启动自动调优 |
| GET | `/api/tuning/status` | 获取调优状态 |

### 6.6 配置管理 API (`/api/config`)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/config/models` | 列出所有 provider 配置 |
| GET | `/api/config/models/:provider` | 获取单个 provider 配置 |
| PUT | `/api/config/models/:provider` | 更新 provider 配置 |
| POST | `/api/config/models/:provider/toggle` | 启用/禁用 provider |
| POST | `/api/config/models/:provider/toggle-model` | 启用/禁用单个子模型 |
| POST | `/api/config/models/:provider/test` | 测试 provider 连通性 |

### 6.7 测试用例 API

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/test-cases/overview` | 测试用例统计概览 |
| GET | `/api/test-cases/all` | 所有测试用例（含题目信息） |
| GET | `/api/questions/:id/test-cases` | 某题的测试用例 |
| POST | `/api/questions/:id/test-cases` | 添加测试用例 |
| PUT | `/api/questions/:id/test-cases/:tc_id` | 更新测试用例 |
| DELETE | `/api/questions/:id/test-cases/:tc_id` | 删除测试用例 |
| POST | `/api/questions/:id/generate-test-cases` | AI 自动生成测试用例 |

### 6.8 评分脚本版本管理 API

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/questions/:id/script-history` | 获取脚本版本历史 |
| POST | `/api/questions/:id/script-rollback` | 回退到指定版本 |

### 6.9 大纲/教材 API

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/syllabus` | 获取大纲/教材列表 |
| POST | `/api/syllabus` | 保存大纲/教材 |
| DELETE | `/api/syllabus/:subject/:type` | 删除大纲/教材 |

---

## 7. 前端架构

### 7.1 页面结构

| 页面 | 文件 | 技术 | 说明 |
|------|------|------|------|
| 登录页 | `templates/login.html` | Vue 3 + Element Plus | 用户选择 + 角色选择 + 科目选择 |
| 题库管理 | `templates/question-bank.html` | Vue 3 + Element Plus | 题目 CRUD、评分标准、模型配置 |
| 测试用例 | `templates/test-cases.html` | Vue 3 + Element Plus | 测试用例管理、验证结果 |
| 评分页 | `dist/index.html` | Vue 3 + Element Plus | 单题评分、模型选择、结果展示 |
| 敏感词管理 | `templates/sensitive-words.html` | Vue 3 + Element Plus | 敏感词 CRUD + 批量导入 |
| 用户管理 | `templates/user-management.html` | Vue 3 + Element Plus | 用户 CRUD（管理员专用） |
| 源码查看 | `static/code-viewer.html` | 原生 HTML/JS | 评分引擎源码查看器 |

### 7.2 登录流程 (v2.1.0)

**登录页** `login.html`:

1. 用户从下拉框选择用户（加载 `GET /api/users`）
2. 选择用户后自动填充角色和科目
3. 选择角色（管理员/科目老师）
4. 科目老师需选择科目
5. 点击进入系统 → localStorage 存储：
   - `ai_grading_role`: admin/teacher
   - `ai_grading_current_subject`: 科目标识
   - `ai_grading_username`: 用户名（用于 student_id 传递）

**评分页** `dist/index.html`:

```javascript
// 提交评分时传递 student_id
const studentId = localStorage.getItem('ai_grading_username') || '';
requestBody = {
    question_id: selectedQuestionId.value,
    answer: studentAnswer.value.trim(),
    student_id: studentId,
    provider: prov,
    model: mdl
};
```

### 7.3 前端页面链接关系

所有页面 Footer 包含统一导航：

```
单题评分 | 题库管理 | 测试集管理 | 敏感词管理 | 用户管理
```

---

## 8. 核心业务流程

### 8.1 评分流程（v2.1.0 完整流程）

```
┌─────────────────────────────────────────────────────────┐
│  用户提交评分请求 (POST /api/grade)                       │
│  含 question_id, answer, student_id, provider, model     │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  1. 空答案预检                                            │
│  stripped = re.sub(r'[\s\W]+', '', answer)               │
│  if len(stripped) < 2 → 0分，model_used='precheck'       │
│  （不记录 student_id 到一致性校验范围）                     │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. 敏感词扫描                                            │
│  check_sensitive_words(answer, subject)                  │
│  high severity 命中 → 0分，model_used='sensitive_filter'  │
│  记录到 bug_log + grading_flags                          │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. 加载题目信息 + 构建 rubric 字典                        │
│  从 DB 加载 question, rubric_script, rubric_rules 等     │
│  合并到 rubric 字典                                       │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  4. LLM 评分（科目分支）                                  │
│  if subject == 'politics':                               │
│      system_prompt = _get_politics_system_prompt()       │
│  else:                                                   │
│      system_prompt = _get_system_prompt()                │
│  3次指数退避重试 (1s/2s/4s)                               │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  5. 输出解析 + 语义校验                                   │
│  _parse_output() → scoring_items 累加总分                │
│  semantic_checker → 语义相似度纠偏                        │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  6. 证据真实性验证                                        │
│  检查 scoring_items 中 quoted_text 是否存在于原始答案     │
│  不存在 → grading_flags + needs_review=True              │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  7. 判别Agent（纯 Python，不调 LLM）                      │
│  - 短答案高分检测：字数<10 且 得分≥80%满分                 │
│  - 全满分检测：所有评分点 hit=true 且 score=max_score     │
│  命中 → grading_flags + needs_review=True                │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  8. 边界检查                                              │
│  - final_score >= 95% max → needs_review                 │
│  - final_score <= 5% max → needs_review                  │
│  - confidence < 0.6 → needs_review                       │
│  - final_score is None → needs_review                    │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  9. 保存评分记录                                          │
│  add_grading_record(question_id, answer, score, ...      │
│      grading_flags=..., student_id=...)                  │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  10. 一致性校验（student_id + question_id 有效时）         │
│  get_previous_grade(student_id, question_id)             │
│  if diff > max_score * 0.2:                              │
│      grading_flags += score_inconsistency                │
│      needs_review = True                                 │
│      UPDATE grading_records SET grading_flags            │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回 JSON 结果                                           │
│  {score, confidence, comment, details, needs_review,     │
│   warning, grading_flags}                                │
└─────────────────────────────────────────────────────────┘
```

### 8.2 聚合评分流程

```
┌─────────────────────────────────────────────────────────┐
│  用户请求聚合评分 (POST /api/grading/single)              │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  engine.aggregate(question, answer, rubric, max_score,   │
│                   sample_count, strategy)                │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  _sample_models()  # 并行调用多模型多次采样                │
│  - asyncio.gather(*tasks)                                │
│  - 每个模型采样 sample_count 次                           │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  根据 strategy 选择聚合策略:                               │
│  ├─ majority_vote: 多数投票                               │
│  ├─ weighted_average: 简单加权平均                        │
│  └─ confidence_weighted: 置信度加权（默认）                │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回 GradingResult                                       │
│  {score, confidence, consistency, needs_review}          │
└─────────────────────────────────────────────────────────┘
```

### 8.3 配置管理流程

```
.env 文件（默认配置）→ config/settings.py → DB model_configs 表 → get_effective_config()
```

**配置优先级**: `数据库配置` > `.env 配置` > `settings.py 默认值`

---

## 9. 核心算法设计

### 9.1 置信度加权算法（默认聚合策略）

```python
def _confidence_weighted(self, results, max_score):
    """
    置信度加权聚合算法

    步骤:
    1. 收集所有模型的评分结果（含多次采样）
    2. 过滤错误响应（confidence=0）
    3. 异常值过滤（MAD 法）：
       - 当采样数 >= 4 时，计算中位数绝对偏差
       - 保留离中位数在 2*MAD 范围内的结果
    4. 加权平均：final_score = np.average(scores, weights=confidence)
    5. 综合置信度：confidence = np.average(weights, weights=weights)
    6. 一致性计算：consistency = 1 - std(scores)/max_score
    7. 最终置信度：(confidence + consistency) / 2
    8. 一致性 < 0.5 时，置信度减半并标记需复核
    """
```

### 9.2 边界检测算法

```python
def boundary_check(self, result: QwenGradingResult) -> QwenGradingResult:
    """
    边界检查 + 分数截断

    规则:
    - final_score is None → needs_review=True（跳过其他检查）
    - final_score >= max_score * 0.95 → needs_review
    - final_score <= max_score * 0.05 → needs_review
    - confidence < threshold_low → needs_review
    - 分数截断到 [0, max_score] 范围
    """
```

### 9.3 判别Agent (v2.1.0)

**纯 Python 检查，不调用 LLM**，在 LLM 评分之后执行：

#### 短答案高分检测 (short_answer_high_score)

```python
if final_score >= max_score * 0.8:
    stripped_answer = re.sub(r'[\s\W]+', '', student_answer)
    if len(stripped_answer) < 10:
        # 触发警告：答案仅N个字但得分X分
```

**目的**: 防止模型给极短答案打高分（P2 缓存幻觉）。

#### 全满分检测 (all_perfect)

```python
if final_score >= max_score * 0.95:
    if scoring_items and len(scoring_items) >= 3:
        scoreable = [i for i in scoring_items if i.get("max_score", 0) > 0]
        if scoreable and all(i.get("hit") and i.get("score") >= i.get("max_score") for i in scoreable):
            # 触发警告：所有N个评分点全部满分
```

**目的**: 防止模型给所有要点判满分（P3 缓存幻觉）。

### 9.4 一致性校验算法 (v2.1.0)

```python
# 在 grade_answer() 中，评分记录保存之后
if student_id and question_id and final_score is not None:
    prev = get_previous_grade(student_id, question_id, exclude_record_id=record_id)
    if prev and prev.get('score') is not None:
        diff = abs(final_score - prev['score'])
        if diff > max_score * 0.2:
            # 触发评分不一致警告
            # 更新 DB grading_flags
```

**核心原则**: 同一学生同一题目，多次评分的分数差异不应超过满分的 20%。

### 9.5 证据真实性验证

```python
if result.scoring_items:
    for item in result.scoring_items:
        quoted = item.get("quoted_text", "")
        if quoted and quoted not in student_answer:
            # 触发 fake_quote 警告
            # 该评分点的引用原文不存在于学生答案中
```

**目的**: 防止 LLM 编造不存在的引用文本（P1 幻觉）。

---

## 10. 配置系统

### 10.1 配置分层

```
第1层：.env 文件（默认配置）
    ↓ load_dotenv()
第2层：config/settings.py（Python 配置对象）
第3层：数据库 model_configs 表（运行时覆盖配置）
第4层：ModelRegistry 中的模型实例
```

**配置优先级**: `数据库配置` > `.env 配置` > `settings.py 默认值`

### 10.2 关键配置项

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DEFAULT_SAMPLE_COUNT` | 默认采样次数 | `3` |
| `DEFAULT_STRATEGY` | 默认聚合策略 | `confidence_weighted` |
| `CONFIDENCE_LOW` | 低置信度阈值 | `0.6` |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `5001` |

---

## 11. 评分一致性保障体系

> **P0 原则**: 任何场景下，同一答案的评分必须一致。任何不一致都需要记录、查因、修复。

### 11.1 问题来源

| 问题编号 | 问题 | 影响 |
|---------|------|------|
| P1 | LLM 引用不存在的原文 (fake_quote) | 评分依据不真实 |
| P2 | 极短答案得高分 (short_answer_high_score) | 评分标准执行不严 |
| P3 | 全部评分点判满分 (all_perfect) | 缓存/偷懒幻觉 |
| P4 | 同题多次评分分数不一致 (score_inconsistency) | 评分不可信 |

### 11.2 保障机制

| 机制 | 层级 | 检测问题 | 实现 |
|------|------|---------|------|
| `temperature=0.0` | LLM 调用 | 输出随机性 | `qwen_engine.py` |
| `cache_buster` | Prompt | API 服务端缓存 | `_build_user_prompt()` |
| 证据真实性验证 | 后处理 | P1 | `api_routes.py:grade_answer()` |
| 短答案高分检测 | 后处理 | P2 | 判别Agent |
| 全满分检测 | 后处理 | P3 | 判别Agent |
| 一致性校验 | 后处理 | P4 | `get_previous_grade()` |
| 边界检查 | 后处理 | 异常分数 | `boundary_check()` |
| 敏感词过滤 | 前置 | 违规内容 | `check_sensitive_words()` |

### 11.3 student_id 数据流

```
前端 localStorage('ai_grading_username')
    ↓ HTTP POST
api_routes.grade_answer() → student_id = data.get('student_id')
    ↓
add_grading_record(..., student_id=student_id)
    ↓
get_previous_grade(student_id, question_id) → 一致性校验
```

---

## 12. 科目专用评分流程

> 三个科目的 rubric_script 格式差异巨大，需要不同的系统提示词和输出解析策略。

### 12.1 科目差异

| 科目 | rubric_script 输出格式 | 特点 |
|------|----------------------|------|
| **思政** | `{"总分":X, "评语":"..."}` | 扁平输出，逐要素判断，有反作弊规则，部分得分（1.5分等） |
| **语文** | `{"第一问":{"得分":X,"满分":2,"评语":"..."},...,"错别字扣分":X,"总分":X}` | 按子问题拆分，有错别字扣分 |
| **英语** | `{"第1问":{"得分":X,"满分":2,"评语":"..."},...,"总分":X}` | 按子问题拆分，子采分点1分1分拆 |

### 12.2 思政专用流程

**系统提示词** (`_get_politics_system_prompt()`):

- 严格按 rubric_script 的【逐项评分规则】执行
- 分值完全按脚本标注，不可自行调整
- 部分得分条件严格执行（如1.5分）
- 等价表述按脚本中的等价表述表匹配
- 输出格式：`{"总分": X, "评语": "..."}`

**解析方式**: 直接从 `{"总分": X}` 取分，评语字段直接使用。

### 12.3 语文专用流程

**系统提示词** (`_get_chinese_system_prompt()`):

- 反作弊优先：复制诗歌原文/题干 → 该问0分（但引用诗句+自己的分析应正常给分）
- 逐项按 rubric_script 的【逐项评分规则】判断
- 错别字扣分：按【扣分规则】执行，每处扣0.5分，扣完该问满分为止
- 部分得分条件严格执行
- 等价表述按脚本中的等价表述表匹配
- 输出格式：**不硬编码 JSON schema**，要求"严格按照评分脚本中【输出格式要求】输出"

**输出格式示例**（由 rubric_script 定义）:

```json
{
  "第一问": {"得分": 2, "满分": 2, "评语": "准确识别边塞诗体裁"},
  "第二问": {"得分": 1, "满分": 4, "评语": "提及环境艰苦但未分析表现手法"},
  "第三问": {"得分": 2, "满分": 4, "评语": "答出爱国情感但未提及建功立业"},
  "错别字扣分": 0.5,
  "总分": 4.5,
  "评语": "整体..."
}
```

**关键差异**:
- `错别字扣分` 字段为语文独有
- 总分 = 各问得分之和 - 错别字扣分
- `_parse_output()` 已有逐问格式兼容逻辑，无需改动

### 12.4 英语专用流程

**系统提示词** (`_get_english_system_prompt()`):

- 全英文提示词，输出 JSON 键名用 `comment` 而非 `评语`
- 反作弊优先：复制阅读材料原文/题干 → 该问0分
- 逐项按 rubric_script 的【逐项评分规则】判断
- **语言规则**：用拼音或中文作答一律判0分
- 等价表述匹配，大小写不敏感
- 输出格式：强制 `scoring_items` 格式（忽略 rubric_script 中可能存在的旧格式要求）

**输出格式**（统一 scoring_items）:

```json
{
  "scoring_items": [
    {"name": "Point 1: Spring Festival", "score": 2, "max_score": 2, "hit": true, "reason": "Correct", "quoted_text": "Spring Festival"},
    {"name": "Point 2: Homophone meaning", "score": 1, "max_score": 2, "hit": true, "reason": "Hit partial", "quoted_text": "surplus"}
  ],
  "comment": "Overall comment..."
}
```

**关键差异**:
- 中文/拼音作答 → 全题0分（语义校验也跳过英语科目）
- 无错别字扣分
- 向量层跳过：`three_layer_grader` 中英语科目不执行 text2vec 向量匹配（中文模型对英文不可靠）
- 语义校验跳过：`semantic_checker` 使用中文 text2vec 模型，不适用于英文
- 评分脚本生成使用 `RUBRIC_SCRIPT_SYSTEM_PROMPT_EN`（全英文）
- 子题评分时自动注入父题阅读材料作为 `[Reading Material]` 前缀
- 短答案高分检测按词数（<5词）而非字数判断
- 前端 UI 自动适配：科目标签、测试集风格选项、placeholder 文本均随科目动态切换

### 12.5 分支路由

```python
if subject == 'politics':
    system_prompt = self._get_politics_system_prompt()
elif subject == 'chinese':
    system_prompt = self._get_chinese_system_prompt()
elif subject == 'english':
    system_prompt = self._get_english_system_prompt()
else:
    system_prompt = self._get_system_prompt()
```

### 12.6 通用系统提示词 (`_get_system_prompt()`)

未匹配到专用流程的科目使用通用提示词，输出 `scoring_items` 格式：

```json
{
  "评语": "评语内容",
  "scoring_items": [
    {
      "name": "要点名称",
      "score": 得分,
      "max_score": 该要点满分,
      "hit": true/false,
      "reason": "原因",
      "quoted_text": "从学生答案中摘录的原文"
    }
  ]
}
```

总分由系统从 `scoring_items` 累加得出，不由模型直接给出。

---

## 13. 部署与运维

### 13.1 启动流程

```bash
# start.sh
1. 检查 .env 文件 → 不存在则从 .env.example 复制
2. pip install -q -r requirements.txt
3. python main.py

# main.py
1. sys.path.insert(0, 项目根目录)
2. from app.app import create_app
3. logger.add("logs/grading_{time}.log", rotation="1 day", retention="7 days")
4. create_app() → app.run(host="0.0.0.0", port=5001, debug=True)
```

### 13.2 数据库备份

```bash
# 备份
cp data/exam_system.db data/exam_system.db.bak.$(date +%Y%m%d)

# 恢复
cp data/exam_system.db.bak.20260410 data/exam_system.db
```

---

## 14. 扩展指南

### 14.1 新增服务商

1. `.env` 添加配置
2. `config/settings.py` 添加 `XXX_CONFIG`
3. `db_models.py` 注册到 `_PROVIDER_DEFAULTS`
4. `app/models/xxx.py` 创建客户端类
5. `ModelProvider` 枚举中添加
6. `registry.py` 注册
7. `config_routes.py` 添加元数据

### 14.2 新增科目专用评分流程

1. 在 `qwen_engine.py` 添加 `_{subject}_system_prompt()` 方法
2. 在 `grade()` 方法的 subject 分支中添加路由
3. 在 `_parse_output()` 中添加该科目的输出格式解析
4. 更新本文档第 12 章

### 14.3 新增判别Agent

1. 在 `api_routes.py:grade_answer()` 的判别Agent 区域添加检测逻辑
2. 定义 `grading_flags` 的 type 和 severity
3. 触发时设置 `result.needs_review = True`

---

## 15. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v2.3.0 | 2026-04-12 | 英语科目全面适配：向量层跳过、阅读材料注入、英文提示词（评分/生成/自查/评估）、前端动态化（科目标签/风格选项/placeholder）、短答案检测按词数、一致性检查支持英文分值格式 |
| v2.2.0 | 2026-04-10 | 语文/英语专用评分流程 + 英语语义校验跳过 |
| v2.1.0 | 2026-04-10 | 用户管理系统 + student_id 追踪 + 一致性校验 + 判别Agent(P2/P3) + 思政专用评分流程 |
| v2.0.0 | 2026-04-09 | 反作弊测试页面 + 多模型子模型选择修复 |
| v2.0.0-beta | 2026-04-08 | 评分页面 Vue 3 + Element Plus 浅色主题重构 |
| v1.5.0 | 2026-04-07 | 侧边栏收起/展开 + config_routes 统一 |
| v1.4.0 | 2026-04-06 | 管理员/科目老师角色分离 + 模型配置管理 |
| v1.3.0 | 2026-04-05 | 评分引擎反作弊优先 + 逐问累加 |
| v1.2.0 | 2026-04-04 | 评分引擎重构 + 科目登录 + 测试用例体系 |
| v1.1.0 | 2026-04-03 | AI 批量出题独立页面 |
| v1.0.1 | 2026-04-02 | 修复评分规则传递和 JS 函数定义 |
| v1.0.0 | 2026-04-01 | AI 智能评分系统 v1.0（初始提交） |

---

## 16. 附录

### 16.1 关键文件清单

| 文件 | 职责 | 关键函数/类 |
|------|------|------------|
| `main.py` | 应用入口 | `create_app()` |
| `app/app.py` | Flask 应用工厂 | `create_app()`, `register_routes()` |
| `app/api_routes.py` | 数据库 API | `grade_answer()`, 判别Agent, 用户/敏感词 API |
| `app/qwen_engine.py` | 主评分引擎 | `grade()`, `_get_politics_system_prompt()`, `_get_chinese_system_prompt()`, `_get_english_system_prompt()` |
| `app/engine.py` | 聚合引擎 | `AggregationEngine.aggregate()` |
| `app/models/db_models.py` | 数据库操作 | `get_effective_config()`, `get_previous_grade()`, 用户 CRUD |
| `templates/login.html` | 登录页 | 用户选择 + 角色/科目选择 |
| `templates/user-management.html` | 用户管理页 | 用户 CRUD |
| `dist/index.html` | 评分页 | student_id 传递 + 结果展示 |

### 16.2 数据库表关系图

```
users (用户表) [独立表]

questions (题目表)
    │
    ├─→ grading_records (评分记录表) [FK: question_id, 含 student_id → users.username]
    ├─→ test_cases (测试用例表) [FK: question_id]
    ├─→ rubric_script_history (评分脚本历史表) [FK: question_id]
    └─→ batch_tasks (批量任务表) [间接关联]

model_configs (模型配置表) [独立表]

sensitive_words (敏感词表) [独立表]

bug_log (Bug 日志表) [独立表]
```

### 16.3 grading_flags 类型一览

| type | severity | 触发条件 | 说明 |
|------|----------|---------|------|
| `fake_quote` | warning | quoted_text 不在原始答案中 | LLM 编造引用 |
| `short_answer_high_score` | warning | 字数 < 10 且得分 ≥ 80% | 短答案高分异常 |
| `all_perfect` | info | 所有评分点满分 | 全满分异常 |
| `score_inconsistency` | warning | 与历史评分差异 > 20% | 评分不一致 |
| `sensitive_word` | error | 命中高危敏感词 | 直接 0 分 |

---

**文档结束**
