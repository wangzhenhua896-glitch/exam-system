# AI 智能评分系统

> 基于大语言模型的简答题自动化评分系统

## 项目简介

本系统利用大语言模型对简答题进行自动化评分，支持多服务商模型配置、评分脚本管理、测试用例验证、反作弊检测等功能。

## 技术栈

- **后端**: Flask + SQLite + OpenAI 兼容接口
- **前端**: Vue 3 + Element Plus（单页应用）
- **评分引擎**: `QwenGradingEngine` — 基于评分脚本的分点给分，支持反作弊检查

## 核心功能

- **单题评分**: 选择题目 → 输入答案 → AI 评分，支持多模型对比
- **题库管理**: 科目分类、评分脚本生成、标准答案管理
- **测试用例**: 保存评分结果为测试用例，批量验证评分一致性
- **多模型配置**: 通过 Web UI 管理模型服务商（豆包/通义/GLM/文心/讯飞/小米等），支持子模型切换
- **反作弊检测**: 复制题干、空白作答、答非所问自动判 0 分

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动
python main.py
# 访问 http://localhost:5001
```

## 页面说明

| 路径 | 功能 |
|------|------|
| `/login` | 登录页 |
| `/management` | 题库管理（科目、题目、评分脚本） |
| `/grading` | 单题评分 |
| `/test-cases` | 测试集管理 |

## 项目结构

```
app/
├── app.py                # Flask 应用工厂
├── api_routes.py         # 主 API（评分/题目/历史/配置）
├── config_routes.py      # 模型配置管理 API
├── qwen_engine.py        # 评分引擎（核心）
├── engine.py             # 多模型聚合引擎（历史遗留）
├── models/
│   └── db_models.py      # SQLite 数据库操作
config/
└── settings.py           # 默认配置
dist/
└── index.html            # 单题评分页（Vue 3 SPA）
templates/
├── question-bank.html    # 题库管理页
├── test-cases.html       # 测试集管理页
└── login.html            # 登录页
data/
└── exam_system.db        # SQLite 数据库
```

## 数据库

| 表 | 用途 |
|----|------|
| `questions` | 题目（含评分脚本 rubric_script） |
| `grading_records` | 评分记录 |
| `test_cases` | 测试用例 |
| `model_configs` | 模型服务商配置 |
| `rubric_script_history` | 评分脚本版本历史 |
| `syllabus` | 教学大纲/教材 |
| `batch_tasks` | 批量任务 |

## 模型配置

模型通过管理页面（`/management` → 模型配置）管理，存储在数据库 `model_configs` 表中。

所有服务商均通过 OpenAI 兼容接口调用，无需安装厂商 SDK。

## 版本

v2.0.0 | 更新日期: 2026-04-10
