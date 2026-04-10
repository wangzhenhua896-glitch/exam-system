# AI 智能评分系统设计文档

> **文档版本**: v2.0.0  
> **最后更新**: 2026-04-09  
> **Git Commit**: bf9c6d9  
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
11. [部署与运维](#11-部署与运维)
12. [扩展指南](#12-扩展指南)
13. [版本历史](#13-版本历史)
14. [附录](#14-附录)

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

### 1.3 设计原则

- **多模型解耦**: 统一 `BaseModelClient` 接口，新增模型只需实现子类
- **配置分层**: `.env` 默认 → Python 配置 → 数据库覆盖，灵活可配
- **异步并发**: 全链路异步设计，支持高并发评分
- **可验证性**: 内置验证引擎和测试数据集，确保评分质量
- **可观测性**: 完整日志记录、评分历史、统计监控

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
│   ├── login.html               # 登录页（角色选择）
│   ├── question-bank.html       # 题库管理（Vue 3 + Element Plus）
│   └── test-cases.html          # 测试用例管理页
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
| `api_bp` | `/api` | `api_routes.py` | 题目 CRUD、评分、统计 |
| `config_bp` | `/api/config` | `config_routes.py` | 模型配置管理 |

**页面路由**:

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | → `/login` | 根路径重定向 |
| `/login` | `login.html` | 登录页（角色选择） |
| `/management` | `question-bank.html` | 题库管理（管理员/科目老师） |
| `/grading` | `dist/index.html` | 单题评分页 |
| `/test-cases` | `test-cases.html` | 测试用例管理 |
| `/code-viewer` | `code-viewer.html` | 评分引擎源码查看 |

### 4.2 主评分引擎 (`app/qwen_engine.py`)

**类**: `QwenGradingEngine`, `QwenGradingResult`

**核心方法**:

| 方法 | 职责 |
|------|------|
| `grade()` | 主入口，3 次指数退避重试（1s/2s/4s） |
| `_init_client()` | 初始化 OpenAI 兼容客户端，DB 配置 → .env 降级 |
| `set_provider()` | 运行时切换服务商和模型 |
| `_format_rubric()` | 格式化评分标准（rubricScript → rules+points 降级） |
| `_get_system_prompt()` | 系统提示词（角色 + 流程 + JSON + 反作弊） |
| `_build_user_prompt()` | 用户提示词（含 cache_buster 破缓存） |
| `_parse_output()` | 解析 LLM JSON 输出，scoring_items 累加总分 |
| `_calculate_confidence()` | 基于输出长度计算置信度 |
| `boundary_check()` | 边界检查 + 分数截断 |

**评分流程**:

```
grade(question, answer, rubric, max_score)
    ↓
_format_rubric(rubric)  # 格式化评分标准
    ↓
_get_system_prompt()    # 系统提示词
_build_user_prompt()    # 用户提示词
    ↓
调用 LLM API（temperature=0.0, max_tokens=4096）
    ↓ 失败重试（指数退避 3 次）
_parse_output(response) # 解析 JSON，累加 scoring_items
    ↓
_calculate_confidence() # 计算置信度
    ↓
boundary_check()        # 边界检测
    ↓
返回 QwenGradingResult(score, confidence, comment, details, needs_review)
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

**多模型注册逻辑**:

```python
def init_models(config: Dict[str, Any]) -> None:
    """
    初始化所有模型
    
    逻辑:
    1. 遍历每个服务商 (qwen, glm, doubao, ...)
    2. 检查服务商是否启用 (config[provider].enabled)
    3. 读取 available_models 列表
    4. 读取 enabled_models 集合 (extra_config)
    5. 为每个启用的子模型:
       - 创建客户端实例
       - 设置 display_name
       - 注册到 model_registry
    """
```

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
| score | REAL | | 得分 |
| details | TEXT | | JSON 详情 |
| model_used | TEXT | | 使用的模型 |
| confidence | REAL | | 置信度 |
| graded_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 评分时间 |

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

**extra_config 结构示例**:

```json
{
    "enabled_models": [
        "deepseek-v3-250324",
        "deepseek-v3-2-251201",
        "doubao-seed-2-0-pro-260215"
    ]
}
```

#### 5.1.6 batch_tasks (批量任务表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| status | TEXT | | 任务状态（pending/running/completed/failed） |
| total_count | INTEGER | | 总题目数 |
| processed_count | INTEGER | | 已处理数 |
| created_at | TIMESTAMP | | 创建时间 |
| completed_at | TIMESTAMP | | 完成时间 |

#### 5.1.7 syllabus (考试大纲表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| subject | TEXT | | 科目 |
| content | TEXT | | 大纲内容 |
| created_at | TIMESTAMP | | 创建时间 |

#### 5.1.8 rubrics (评分规则表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| name | TEXT | | 规则名称 |
| content | TEXT | | 规则内容 |
| created_at | TIMESTAMP | | 创建时间 |

#### 5.1.9 bug_log (Bug 日志表)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 自增主键 |
| description | TEXT | | Bug 描述 |
| status | TEXT | | 状态（open/fixed） |
| created_at | TIMESTAMP | | 创建时间 |

### 5.2 数据库操作模块 (`db_models.py`)

**关键函数**:

| 函数 | 说明 |
|------|------|
| `init_database()` | 初始化数据库，创建所有表 |
| `get_db_connection()` | 获取数据库连接 |
| `get_effective_config(provider)` | 获取服务商有效配置（DB → .env 降级） |
| `get_all_effective_configs()` | 获取所有服务商配置 |
| `upsert_model_config(...)` | 新增或更新模型配置 |
| `toggle_model_enabled(provider, enabled)` | 切换服务商启用状态 |
| `add_question(...)` | 添加题目 |
| `get_question(id)` | 获取题目详情 |
| `add_grading_record(...)` | 添加评分记录 |

---

## 6. API 接口设计

### 6.1 评分 API (`/api/grading`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/grading/single` | 单题评分 | `{question, answer, rubric, max_score, sample_count, strategy}` | `{success, result}` |
| GET | `/api/grading/models` | 列出可用模型 | - | `{success, models}` |
| GET | `/api/grading/strategies` | 列出可用策略 | - | `{success, strategies}` |

### 6.2 批量 API (`/api/batch`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/batch/grade` | 批量评分 | `{questions, rubric, max_score}` | `{success, results}` |
| POST | `/api/batch/test` | 性能测试 | `{count, sample_count}` | `{success, stats}` |

### 6.3 数据库 API (`/api`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/providers` | 列出已启用的 provider 及子模型 | - | `{success, data}` |
| GET | `/api/questions` | 获取题目列表 | `?subject=xxx` | `{success, questions}` |
| GET | `/api/questions/:id` | 获取题目详情 | - | `{success, question}` |
| POST | `/api/questions` | 创建题目 | `{subject, title, content, rubric, ...}` | `{success, id}` |
| PUT | `/api/questions/:id` | 更新题目 | 同创建 | `{success}` |
| DELETE | `/api/questions/:id` | 删除题目 | - | `{success}` |
| POST | `/api/grade` | 评分答案（Qwen 引擎） | `{question_id, answer, provider, model, rubric, max_score}` | `{success, score, confidence, comment, details, needs_review, warning}` |
| GET | `/api/history` | 获取评分历史 | `?question_id=xxx` | `{success, records}` |
| POST | `/api/batch` | 创建批量评分任务 | `{question_ids, rubric}` | `{success, task_id}` |
| GET | `/api/batch/:id` | 获取批量任务状态 | - | `{success, status, progress}` |
| GET | `/api/stats` | 获取统计信息 | - | `{success, stats}` |
| GET | `/api/dashboard` | 题库总览（含科目过滤） | `?subject=xxx` | `{success, data}` |
| GET | `/api/export-rubric-scripts` | 导出评分脚本（Markdown） | - | Markdown 文件 |
| GET | `/api/models/available` | 获取所有可用模型列表 | - | `{success, models}` |

### 6.4 验证 API (`/api/validation`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/validation/run` | 运行评分规则验证 | `{strategy, sample_count}` | `{success, validation_result}` |
| GET | `/api/validation/dataset` | 获取测试数据集信息 | - | `{success, dataset}` |

### 6.5 调优 API (`/api/tuning`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/tuning/start` | 启动自动调优 | `{max_iterations, target_accuracy, target_correlation}` | `{success, tuning_result}` |
| GET | `/api/tuning/status` | 获取调优状态 | - | `{success, status, progress}` |

### 6.6 配置管理 API (`/api/config`)

| 方法 | 路由 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/config/models` | 列出所有 provider 配置 | - | `{success, providers}` |
| GET | `/api/config/models/:provider` | 获取单个 provider 配置 | - | `{success, config}` |
| PUT | `/api/config/models/:provider` | 更新 provider 配置 | `{api_key, base_url, model, enabled}` | `{success}` |
| POST | `/api/config/models/:provider/toggle` | 启用/禁用 provider | `{enabled}` | `{success}` |
| POST | `/api/config/models/toggle-all` | 批量启用/禁用全部 | `{enabled}` | `{success}` |
| POST | `/api/config/models/:provider/toggle-model` | 启用/禁用单个子模型 | `{model_id, enabled}` | `{success}` |
| POST | `/api/config/models/:provider/test` | 测试单个 provider 连通性 | - | `{success, provider, latency_ms, error}` |
| POST | `/api/config/models/test-all` | 测试所有已启用 provider | - | `{success, results}` |

---

## 7. 前端架构

### 7.1 页面结构

| 页面 | 文件 | 技术 | 说明 |
|------|------|------|------|
| 登录页 | `templates/login.html` | Vue 3 + Element Plus | 角色选择（管理员/科目老师） |
| 题库管理 | `templates/question-bank.html` | Vue 3 + Element Plus | 题目 CRUD、评分标准配置、模型配置管理 |
| 测试用例 | `templates/test-cases.html` | Vue 3 + Element Plus | 测试用例管理、验证结果展示 |
| 评分页 | `dist/index.html` | Vue 3 + Element Plus | 单题评分、模型选择、结果展示 |
| 源码查看 | `static/code-viewer.html` | 原生 HTML/JS | 评分引擎源码查看器 |

### 7.2 前端技术栈

- **框架**: Vue 3 (Composition API)
- **UI 库**: Element Plus
- **HTTP 客户端**: Axios
- **状态管理**: Vue 3 `reactive` + `ref` + `computed`
- **构建**: 无构建工具，直接加载 `vue.global.prod.js`

### 7.3 核心前端组件

#### 题库管理页面 (`question-bank.html`)

**功能模块**:
- 题目列表（分页、搜索、科目过滤）
- 题目编辑（表单、评分标准配置）
- 模型配置管理（服务商开关、子模型开关、连通性测试）
- 评分脚本管理（版本历史、导出）

**关键数据**:
```javascript
const questions = ref([])
const modelConfigs = ref([])
const editingModelConfig = ref(null)
```

#### 评分页面 (`dist/index.html`)

**功能模块**:
- 模型选择（按服务商分组下拉框）
- 评分表单（题目、答案、评分标准）
- 评分结果展示（分数、置信度、评分理由）
- 系统配置（采样次数、温度、置信度阈值）

**模型分组逻辑**:
```javascript
const modelGroups = computed(() => {
    const providerLabels = { 
        qwen: '通义千问', 
        glm: '智谱 GLM', 
        doubao: '火山引擎 ARK',
        // ...
    };
    const groups = {};
    // 只显示 enabled=true 的模型
    availableModels.value.filter(m => m.enabled).forEach(m => {
        const p = m.provider || 'other';
        if (!groups[p]) groups[p] = { provider: p, label: providerLabels[p], models: [] };
        groups[p].models.push(m);
    });
    return Object.values(groups);
});
```

### 7.4 前端路由逻辑

无前端路由，使用菜单切换：

```javascript
const handleMenuSelect = (index) => { currentPage.value = index; }
```

---

## 8. 核心业务流程

### 8.1 评分流程（主流程 - QwenGradingEngine）

```
┌─────────────────────────────────────────────────────────┐
│  用户提交评分请求 (POST /api/grade)                       │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  api_routes.grade_answer()                               │
│  - 解析请求参数（question_id/answer/provider/model/...）  │
│  - 如有 question_id → 从数据库加载题目信息                │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  grading_engine.set_provider(provider, model)            │
│  （如前端指定，否则使用默认配置）                          │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  grading_engine.grade(question, answer, rubric, max_score)│
│  ├─ _format_rubric()                                     │
│  ├─ _get_system_prompt()                                 │
│  ├─ _build_user_prompt()                                 │
│  ├─ 调用 LLM（3次指数退避重试: 1s/2s/4s）                 │
│  ├─ _parse_output()                                      │
│  ├─ _calculate_confidence()                              │
│  └─ boundary_check()                                     │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  add_grading_record()  # 保存评分记录到数据库              │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回 JSON 结果                                           │
│  {score, confidence, comment, details, needs_review}     │
└─────────────────────────────────────────────────────────┘
```

### 8.2 聚合评分流程

```
┌─────────────────────────────────────────────────────────┐
│  用户请求聚合评分 (POST /api/grading/single)              │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  engine.aggregate(question, answer, rubric, max_score,    │
│                   sample_count, strategy)                 │
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
│  _boundary_check()  # 边界检测                            │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回 GradingResult                                       │
│  {score, confidence, consistency, needs_review}          │
└─────────────────────────────────────────────────────────┘
```

### 8.3 配置管理流程

```
┌─────────────────────────────────────────────────────────┐
│  .env 文件（默认配置）                                     │
└────────────────────┬────────────────────────────────────┘
                     ▼ 系统启动时
┌─────────────────────────────────────────────────────────┐
│  config/settings.py 读取环境变量                           │
│  → QWEN_CONFIG/GLM_CONFIG/...                            │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  db_models._get_env_defaults() 缓存 .env 默认值           │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  数据库 model_configs 表                                  │
│  （管理员通过 Web UI 修改的覆盖配置）                       │
└────────────────────┬────────────────────────────────────┘
                     ▼ 查询时
┌─────────────────────────────────────────────────────────┐
│  db_models.get_effective_config(provider)                │
│  优先: 数据库配置 (if exists and enabled)                 │
│  降级: .env 默认值                                        │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  registry.py init_models() 注册模型到 ModelRegistry       │
└─────────────────────────────────────────────────────────┘
```

### 8.4 模型注册流程

```
┌─────────────────────────────────────────────────────────┐
│  应用启动 (app/routes.py)                                 │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  get_all_effective_configs()                             │
│  - 从 DB 读取有效配置                                     │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  init_models(_model_config)  # registry.py               │
│  - 遍历每个 provider                                     │
│  - 检查 enabled 和 api_key                               │
│  - 如有 available_models:                                │
│      为每个启用的子模型创建独立实例                        │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  model_registry.register(client)                         │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  engine = AggregationEngine(GRADING_CONFIG)              │
└─────────────────────────────────────────────────────────┘
```

### 8.5 验证与调优流程

```
┌─────────────────────────────────────────────────────────┐
│  用户启动验证 (POST /api/validation/run)                  │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ValidationEngine.validate()                             │
│  - 加载测试数据集（test_data.py）                         │
│  - 并行评分所有测试项                                     │
│  - 计算统计指标（准确率、误差、相关系数）                   │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回验证结果                                              │
│  {accuracy, avg_error, std_error, max_error, correlation} │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  用户启动调优 (POST /api/tuning/start)                    │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  AutoTuningEngine.tune()                                 │
│  - 迭代调优循环（最大 10 次）                              │
│  - 运行验证 → 计算综合得分 → 检查目标                      │
│  - 参数调整（温度、提示词模板）                            │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  返回调优结果                                              │
│  {best_params, final_accuracy, final_correlation, ...}   │
└─────────────────────────────────────────────────────────┘
```

---

## 9. 核心算法设计

### 9.1 置信度加权算法（默认聚合策略）

**算法步骤**:

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

**MAD 异常值过滤**:

```python
# 中位数绝对偏差 (Median Absolute Deviation)
median = np.median(scores)
mad = np.median(np.abs(scores - median))

# 保留离中位数在 2*MAD 范围内的结果
threshold = 2 * mad
filtered = [(s, c) for s, c in zip(scores, confidences) 
            if abs(s - median) <= threshold]
```

### 9.2 多数投票算法

```python
def _majority_vote(self, results, max_score):
    """
    多数投票算法
    
    步骤:
    1. 分数离散化为整数
    2. Counter 统计投票
    3. 取最高票作为最终分数
    4. 置信度 = 最高票比例
    """
    from collections import Counter
    
    # 离散化分数
    int_scores = [int(round(r.score)) for r in results]
    
    # 统计投票
    vote_counts = Counter(int_scores)
    final_score, vote_count = vote_counts.most_common(1)[0]
    
    # 计算置信度
    confidence = vote_count / len(int_scores)
    
    return final_score, confidence
```

### 9.3 边界检测算法

```python
def _boundary_check(self, final_score, max_score, confidence):
    """
    边界检测算法
    
    规则:
    - final_score >= max_score * 0.95 → "接近满分，建议复核"
    - final_score <= max_score * 0.05 → "接近零分，建议复核"
    - confidence < 0.6 → "置信度过低，必须复核"
    """
    warnings = []
    needs_review = False
    
    if final_score >= max_score * 0.95:
        warnings.append("接近满分，建议复核")
        needs_review = True
    
    if final_score <= max_score * 0.05:
        warnings.append("接近零分，建议复核")
        needs_review = True
    
    if confidence < 0.6:
        warnings.append("置信度过低，必须复核")
        needs_review = True
    
    return needs_review, warnings
```

### 9.4 自动调优算法

```python
def tune(self, max_iterations=10, target_accuracy=0.8, target_correlation=0.85):
    """
    自动调优算法
    
    迭代调优循环:
    1. 运行验证（ValidationEngine.validate）
    2. 计算综合得分 = accuracy * 0.6 + correlation * 0.4
    3. 检查目标：accuracy >= 0.8 AND correlation >= 0.85
    4. 参数调整：
       - 误差 > 3.0 → 降低温度（-0.05，最低 0.1）
       - 误差 < 1.5 AND correlation > 0.9 → 提高温度（+0.02，最高 0.5）
       - 每 3 次迭代且 accuracy < 0.7 → 切换提示词模板
         模板序列：default → detailed → strict → flexible
    """
```

---

## 10. 配置系统

### 10.1 配置分层

系统使用**四层配置**架构:

```
第1层：.env 文件（默认配置）
    ↓ load_dotenv()
第2层：config/settings.py（Python 配置对象）
    - QWEN_CONFIG, GLM_CONFIG, ... 从 os.getenv() 读取
    - GRADING_CONFIG 定义评分参数
    - SERVER_CONFIG 定义 Web 服务参数
    ↓ 系统启动时
第3层：数据库 model_configs 表（运行时覆盖配置）
    - 管理员通过 Web UI (/api/config/models/:provider PUT) 修改
    - get_effective_config() 优先 DB → 降级 .env
    ↓ 模型注册
第4层：ModelRegistry 中的模型实例
    - 使用最终合并的配置初始化客户端
```

**配置优先级**: `数据库配置` > `.env 配置` > `settings.py 默认值`

### 10.2 关键配置项

#### 模型开关

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `QWEN_ENABLED` | 通义千问开关 | `true` |
| `GLM_ENABLED` | 智谱 GLM 开关 | `false` |
| `MINIMAX_ENABLED` | MiniMax 开关 | `false` |
| `ERNIE_ENABLED` | 百度文心开关 | `false` |
| `DOUBAO_ENABLED` | 字节豆包开关 | `false` |

#### 评分参数

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DEFAULT_SAMPLE_COUNT` | 默认采样次数 | `3` |
| `DEFAULT_STRATEGY` | 默认聚合策略 | `confidence_weighted` |
| `CONFIDENCE_LOW` | 低置信度阈值 | `0.6` |
| `CONFIDENCE_MEDIUM` | 中置信度阈值 | `0.7` |
| `CONFIDENCE_HIGH` | 高置信度阈值 | `0.8` |

#### Web 服务

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `5001` |
| `FLASK_DEBUG` | 调试模式 | `false` |

### 10.3 服务商配置示例

```python
# config/settings.py

DOUBAO_CONFIG = {
    "api_key": os.getenv("DOUBAO_API_KEY", ""),
    "base_url": os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
    "model": os.getenv("DOUBAO_MODEL", "deepseek-v3-250324"),
    "enabled": os.getenv("DOUBAO_ENABLED", "false").lower() == "true",
    
    # 可用模型列表（关键！）
    "available_models": [
        {"id": "deepseek-v3-250324", "name": "DeepSeek-V3"},
        {"id": "deepseek-v3-2-251201", "name": "DeepSeek-V3.2"},
        {"id": "doubao-seed-2-0-pro-260215", "name": "豆包 Seed 2.0 Pro"},
        {"id": "doubao-seed-2-0-lite-260215", "name": "豆包 Seed 2.0 Lite"},
        {"id": "doubao-seed-2-0-mini-260215", "name": "豆包 Seed 2.0 Mini"},
        # ... 更多模型
    ],
}
```

---

## 11. 部署与运维

### 11.1 启动流程

```bash
# start.sh
1. 检查 .env 文件 → 不存在则从 .env.example 复制
2. pip install -q -r requirements.txt
3. python main.py

# main.py
1. sys.path.insert(0, 项目根目录)
2. from app.app import create_app
3. logger.add("logs/grading_{time}.log", rotation="1 day", retention="7 days")
4. create_app():
   - 创建 Flask 实例
   - 配置 SECRET_KEY
   - 启用 CORS
   - register_routes(app)
   - register_error_handlers(app)
5. app.run(host="0.0.0.0", port=5001, debug=True)
```

### 11.2 日志管理

**日志配置** (`main.py`):

```python
from loguru import logger

logger.add(
    "logs/grading_{time}.log",
    rotation="1 day",      # 每天轮转
    retention="7 days",    # 保留 7 天
    level="INFO"
)
```

**日志目录**: `logs/`

### 11.3 数据库备份

**数据库文件**: `data/exam_system.db`

**备份建议**:
```bash
# 备份数据库
cp data/exam_system.db data/exam_system.db.bak.$(date +%Y%m%d)

# 恢复数据库
cp data/exam_system.db.bak.20260409 data/exam_system.db
```

### 11.4 监控指标

**关键指标**:
- 评分响应时间（目标：< 5s）
- 评分准确率（目标：≥ 80%）
- 系统可用性（目标：≥ 99%）
- 数据库大小（定期清理历史记录）

---

## 12. 扩展指南

### 12.1 新增服务商

**步骤 1**: 在 `.env` 添加配置

```bash
NEWPROVIDER_API_KEY=xxx
NEWPROVIDER_BASE_URL=https://api.example.com
NEWPROVIDER_MODEL=model-v1
NEWPROVIDER_ENABLED=false
```

**步骤 2**: 在 `config/settings.py` 添加配置

```python
NEWPROVIDER_CONFIG = {
    "api_key": os.getenv("NEWPROVIDER_API_KEY", ""),
    "base_url": os.getenv("NEWPROVIDER_BASE_URL", "..."),
    "model": os.getenv("NEWPROVIDER_MODEL", "model-v1"),
    "enabled": os.getenv("NEWPROVIDER_ENABLED", "false").lower() == "true",
    "available_models": [
        {"id": "model-v1", "name": "Model V1"},
        {"id": "model-v2", "name": "Model V2"},
    ],
}
```

**步骤 3**: 在 `db_models.py` 注册默认配置

```python
def _get_env_defaults():
    global _PROVIDER_DEFAULTS
    if not _PROVIDER_DEFAULTS:
        from config.settings import (
            QWEN_CONFIG, GLM_CONFIG, ..., NEWPROVIDER_CONFIG
        )
        _PROVIDER_DEFAULTS = {
            'qwen': QWEN_CONFIG,
            # ...
            'newprovider': NEWPROVIDER_CONFIG,  # 添加这里
        }
    return _PROVIDER_DEFAULTS
```

**步骤 4**: 创建客户端类 `app/models/newprovider.py`

```python
from .base import BaseModelClient, ModelResponse, ModelProvider

class NewProviderClient(BaseModelClient):
    provider = ModelProvider.NEWPROVIDER  # 需要在 ModelProvider 枚举中添加
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model", "model-v1")
        self.display_name = config.get("display_name", self.model_name)
        # 初始化客户端...
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        # 实现 API 调用逻辑
        pass
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "display_name": self.display_name,
            "enabled": self.enabled,
        }
```

**步骤 5**: 在 `ModelProvider` 枚举中添加

```python
# app/models/base.py
class ModelProvider(Enum):
    QWEN = "qwen"
    GLM = "glm"
    # ...
    NEWPROVIDER = "newprovider"  # 添加这里
```

**步骤 6**: 在 `registry.py` 注册

```python
def init_models(config: Dict[str, Any]) -> None:
    # ... 其他服务商
    
    # 新增服务商
    newprovider_cfg = config.get("newprovider", {})
    if newprovider_cfg.get("enabled", False):
        try:
            from .newprovider import NewProviderClient
            enabled_models = set(newprovider_cfg.get("extra_config", {}).get("enabled_models", []))
            available_models = newprovider_cfg.get("available_models", [])
            
            if available_models:
                for model_info in available_models:
                    model_id = model_info["id"]
                    if not enabled_models or model_id in enabled_models:
                        model_cfg = {
                            **newprovider_cfg,
                            "model": model_id,
                            "display_name": model_info.get("name", model_id),
                        }
                        client = NewProviderClient(model_cfg)
                        model_registry.register(client)
            else:
                client = NewProviderClient(newprovider_cfg)
                model_registry.register(client)
        except ImportError as e:
            print(f"⚠️  新服务商需要安装 SDK: {e}")
```

**步骤 7**: 在 `config_routes.py` 添加元数据

```python
PROVIDER_META = {
    'qwen': {...},
    # ...
    'newprovider': {
        'name': '新服务商 (NewProvider)',
        'defaults': NEWPROVIDER_CONFIG,
        'available_models': NEWPROVIDER_CONFIG.get('available_models', []),
    },
}
```

### 12.2 新增聚合策略

**步骤 1**: 在 `engine.py` 添加策略方法

```python
def _new_strategy(self, results, max_score):
    """
    新聚合策略
    
    Args:
        results: 评分结果列表
        max_score: 满分
    
    Returns:
        (final_score, confidence)
    """
    # 实现算法
    pass
```

**步骤 2**: 在 `aggregate()` 方法中添加策略选择

```python
if strategy == 'new_strategy':
    final_score, confidence = self._new_strategy(results, max_score)
```

**步骤 3**: 在 `routes.py` 添加策略到列表

```python
@grading_bp.route("/strategies", methods=["GET"])
def list_strategies():
    return jsonify({
        "success": True,
        "strategies": [
            {"id": "majority_vote", "name": "多数投票"},
            {"id": "weighted_average", "name": "加权平均"},
            {"id": "confidence_weighted", "name": "置信度加权"},
            {"id": "new_strategy", "name": "新策略"},  # 添加这里
        ]
    })
```

---

## 13. 版本历史

| 版本 | 日期 | Git Commit | 变更内容 |
|------|------|------------|---------|
| v2.0.0 | 2026-04-09 | bf9c6d9 | 反作弊测试页面 + 多模型子模型选择修复 |
| v2.0.0-beta | 2026-04-08 | 9d5497d | 评分页面 Vue 3 + Element Plus 浅色主题重构 |
| v1.5.0 | 2026-04-07 | 3fcd546 | 侧边栏收起/展开 + config_routes 统一 |
| v1.4.0 | 2026-04-06 | 6842a3d | 管理员/科目老师角色分离 + 模型配置管理 |
| v1.3.0 | 2026-04-05 | 29297b0 | 评分引擎反作弊优先 + 逐问累加 |
| v1.2.0 | 2026-04-04 | e2f67c | 评分引擎重构 + 科目登录 + 测试用例体系 |
| v1.1.0 | 2026-04-03 | b450ee4 | AI 批量出题独立页面 |
| v1.0.1 | 2026-04-02 | 34511b3 | 修复评分规则传递和 JS 函数定义 |
| v1.0.0 | 2026-04-01 | a569234 | AI 智能评分系统 v1.0（初始提交） |

---

## 14. 附录

### 14.1 关键文件清单

| 文件 | 职责 | 关键函数/类 |
|------|------|------------|
| `main.py` | 应用入口 | `create_app()` |
| `app/app.py` | Flask 应用工厂 | `create_app()`, `register_routes()` |
| `app/routes.py` | 评分 API | `grade_single()`, `list_models()` |
| `app/api_routes.py` | 数据库 API | `grade_answer()`, `list_questions()` |
| `app/engine.py` | 聚合引擎 | `AggregationEngine.aggregate()` |
| `app/qwen_engine.py` | 主评分引擎 | `QwenGradingEngine.grade()` |
| `app/validation.py` | 验证引擎 | `ValidationEngine.validate()` |
| `app/auto_tuning.py` | 调优引擎 | `AutoTuningEngine.tune()` |
| `app/models/base.py` | 基础客户端类 | `BaseModelClient`, `ModelProvider` |
| `app/models/registry.py` | 模型注册表 | `ModelRegistry`, `init_models()` |
| `app/models/db_models.py` | 数据库操作 | `get_effective_config()`, `init_database()` |
| `config/settings.py` | 全局配置 | `QWEN_CONFIG`, `GRADING_CONFIG` |
| `templates/question-bank.html` | 题库管理页面 | Vue 3 组件 |
| `dist/index.html` | 评分页面 | Vue 3 组件 |

### 14.2 依赖清单

**Python 依赖** (`requirements.txt`):

```
Flask==3.0.2
flask-cors==4.0.0
openai==1.12.0
zhipuai==2.0.1
qianfan==0.3.0
httpx==0.27.0
pydantic==2.6.3
pydantic-settings==2.1.0
numpy==1.26.4
pandas==2.2.1
loguru==0.7.2
aiohttp==3.9.3
python-dotenv==1.0.1
```

### 14.3 数据库表关系图

```
questions (题目表)
    │
    ├─→ grading_records (评分记录表) [FK: question_id]
    ├─→ test_cases (测试用例表) [FK: question_id]
    ├─→ rubric_script_history (评分脚本历史表) [FK: question_id]
    └─→ batch_tasks (批量任务表) [间接关联]

model_configs (模型配置表) [独立表]

syllabus (考试大纲表) [独立表]

rubrics (评分规则表) [独立表]

bug_log (Bug 日志表) [独立表]
```

### 14.4 错误码说明

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 14.5 常见问题

**Q1: 模型评分失败怎么办？**

A: 检查以下几点：
1. 模型是否启用（`enabled=true`）
2. API Key 是否配置正确
3. 网络连接是否正常
4. 查看日志 `logs/grading_*.log`

**Q2: 如何切换评分模型？**

A: 在评分页面的"模型配置"下拉框选择即可。

**Q3: 如何提高评分准确率？**

A: 使用"验证与调优"功能：
1. 运行验证，查看当前准确率
2. 启动自动调优，迭代优化参数
3. 调整评分标准（rubric_script）

**Q4: 数据库如何备份？**

A: 直接复制 `data/exam_system.db` 文件即可。

---

**文档结束**

如有问题或建议，请联系维护团队。

**文档版本**: v2.0.0  
**最后更新**: 2026-04-09  
**Git Commit**: bf9c6d9
