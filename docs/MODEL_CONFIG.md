# 火山引擎 ARK Coding Plan 多模型集成

## 背景

系统原本仅通过 `.env` 配置单个模型（通义千问），现接入火山引擎 ARK Coding Plan，通过一个 API Key 和统一端点可用多个模型，用于单模型评分调优和后续多模型评分差异分析。

## 接入服务商

| 项目 | 值 |
|------|-----|
| 服务商 | 火山引擎 ARK |
| API 地址 | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| 协议 | OpenAI 兼容（`openai.OpenAI` / `openai.AsyncOpenAI`） |
| 额度 | Coding Plan |

## 可用模型（实测通过）

coding plan 有独立的模型列表，与标准 `/api/v3` 端点不同。以下 8 个模型经实际调用验证可用：

| 模型名称 | Model ID | 来源 |
|----------|----------|------|
| DeepSeek-V3 | `deepseek-v3-250324` | DeepSeek |
| DeepSeek-V3.2 | `deepseek-v3-2-251201` | DeepSeek |
| 豆包 Seed 2.0 Pro | `doubao-seed-2-0-pro-260215` | 字节跳动 |
| 豆包 Seed 2.0 Lite | `doubao-seed-2-0-lite-260215` | 字节跳动 |
| 豆包 Seed 2.0 Mini | `doubao-seed-2-0-mini-260215` | 字节跳动 |
| 豆包 Seed 2.0 Code | `doubao-seed-2-0-code-preview-260215` | 字节跳动 |
| 豆包 Seed Code | `doubao-seed-code-preview-251028` | 字节跳动 |
| GLM-4-7 | `glm-4-7-251222` | 智谱 |

## 架构设计

### 当前阶段：单模型评分

- 默认使用 `deepseek-v3-250324` 通过 `QwenGradingEngine` 评分
- 模型配置页面可切换默认评分模型
- 评分脚本调优阶段只用一个模型，保证一致性

### 后续阶段：多模型差异分析

- 评分脚本调优达标后，启用 `AggregationEngine` + `model_registry` 做多模型交叉验证
- 8 个模型全部注册在 `model_registry` 中，随时可启用
- 对比不同模型对同一批测试用例的评分差异，评估脚本鲁棒性

### 两套引擎的关系

| 引擎 | 文件 | 用途 | 当前状态 |
|------|------|------|---------|
| `QwenGradingEngine` | `app/qwen_engine.py` | 单模型评分（主力） | **活跃使用** |
| `AggregationEngine` + `model_registry` | `app/engine.py` + `app/models/registry.py` | 多模型聚合评分 | 已注册模型，待启用 |

## 文件变更

### `config/settings.py`

- `DOUBAO_CONFIG.base_url` 改为 coding plan 端点
- `DOUBAO_CONFIG.model` 默认值改为 `deepseek-v3-250324`
- 新增 `DOUBAO_CONFIG.available_models` 列表（8 个模型）

### `app/models/registry.py`

- `init_models()` 中 `doubao` 分支：从注册 1 个模型改为遍历 `available_models`，为每个模型创建独立 `DoubaoClient` 实例

### `app/models/doubao.py`

- 构造函数新增 `display_name` 字段
- 新增 `get_info()` 方法，返回包含 `display_name` 的信息

### `app/routes.py`

- 导入 `DOUBAO_CONFIG`，加入 `_model_config` 字典传给 `init_models()`

### `app/api_routes.py`

- 新增 `GET /api/models/available` — 返回所有已注册模型列表
- 新增 `POST /api/models/available` — 保存默认模型配置

### `templates/index.html`

- 模型配置页面：下拉框改为从后端动态加载，按服务商分组
- 底部新增已注册模型表格
- `saveModelConfig` 改为调用后端 API

## .env 配置

```bash
# 火山引擎 ARK Coding Plan
DOUBAO_API_KEY=e85881ca-ba3a-4206-992f-2465342ee838
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
DOUBAO_MODEL=deepseek-v3-250324
DOUBAO_ENABLED=true
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models/available` | 获取所有已注册模型（名称、ID、服务商、状态） |
| POST | `/api/models/available` | 保存默认模型配置 `{ default_model: "model-id" }` |
| GET | `/api/grading/models` | 多模型引擎的模型列表（遗留路由） |

## 验证

```bash
# 启动服务
python main.py

# 检查注册模型数量
curl http://localhost:5005/api/models/available | python -m json.tool

# 预期返回 8 个模型，provider 均为 doubao，enabled 均为 true
```
