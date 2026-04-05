# AI 智能评分系统 - 项目总结

## 📊 项目概览

| 项目 | 说明 |
|------|------|
| **名称** | AI Grading System v2.0 |
| **用途** | 基于国产大模型的简答题自动化评分系统 |
| **目标性能** | 10 分钟完成 1000 份试卷批改 |
| **技术栈** | Python + Flask + 国产大模型 |
| **代码量** | 17 个文件，144KB |

## 🤖 国产大模型替代方案

| 原系统模型 | 替代国产模型 | 提供商 | API |
|-----------|-------------|--------|-----|
| GPT-4o | 通义千问 (Qwen) | 阿里云 | DashScope |
| Claude-3 | 智谱 GLM | 智谱 AI | Open API |
| Gemini-Pro | MiniMax | MiniMax | Open API |
| (备用) | 文心一言 (ERNIE) | 百度 | 千帆 API |
| (备用) | 讯飞星火 | 科大讯飞 | Open API |

## 📁 完整项目结构

```
ai-grading-system/
├── app/
│   ├── __init__.py                    # 包初始化
│   ├── app.py                         # Flask 应用工厂
│   ├── routes.py                      # 评分 API 路由
│   ├── batch_routes.py                # 批量评分路由
│   ├── engine.py                      # 聚合引擎（多模型投票）
│   └── models/
│       ├── __init__.py                # 模型包导出
│       ├── base.py                    # 基础模型接口
│       ├── qwen.py                    # 通义千问客户端
│       ├── glm.py                     # 智谱 GLM 客户端
│       ├── minimax.py                 # MiniMax 客户端
│       ├── ernie.py                   # 百度文心客户端
│       └── registry.py                # 模型注册表
├── config/
│   └── settings.py                    # 系统配置
├── static/
│   ├── css/
│   │   └── style.css                  # 前端样式 (620 行)
│   └── js/
│       └── app.js                     # 前端逻辑 (350 行)
├── templates/
│   └── index.html                     # 主页面 (260 行)
├── tests/                             # 测试目录
├── data/                              # 数据目录
├── logs/                              # 日志目录
├── main.py                            # 主入口
├── requirements.txt                   # Python 依赖
├── .env.example                       # 环境变量示例
└── README.md                          # 项目文档
```

## ✨ 核心功能实现

### 1. 多模型集成投票 ✅
- 支持 5 个国产大模型
- 每个模型独立评分
- 结果聚合提高准确性

### 2. 多次采样与聚合策略 ✅
- 可配置 1/3/5/7 次采样
- 3 种聚合策略：
  - 置信度加权（默认）
  - 加权平均
  - 多数投票

### 3. 置信度校准与边界检测 ✅
- 三级阈值：0.6/0.7/0.8
- 低置信度自动标记复核
- 满分/零分极端值预警

### 4. 单题与批量评分 ✅
- 单题快速评分界面
- 批量性能测试
- 实时进度和统计

## 🎨 前端界面

### 页面模块
| 页面 | 功能 |
|------|------|
| 单题评分 | 题目输入、答案提交、结果展示 |
| 批量测试 | 性能测试、吞吐量统计 |
| 评分配置 | 模型管理、阈值设置 |
| 历史记录 | 评分历史查看 |

### 设计特点
- 深色主题
- 响应式布局
- 实时状态指示
- Toast 通知系统

## 🚀 启动方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 3. 启动系统
python main.py

# 4. 访问界面
http://localhost:5000
```

## 📊 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页面 |
| `/api/grading/single` | POST | 单题评分 |
| `/api/grading/models` | GET | 列出模型 |
| `/api/grading/strategies` | GET | 列出策略 |
| `/api/batch/grade` | POST | 批量评分 |
| `/api/batch/test` | POST | 性能测试 |

## 🔧 配置示例

```bash
# 通义千问
QWEN_API_KEY=your-key
QWEN_ENABLED=true

# 智谱 GLM
GLM_API_KEY=your-key
GLM_ENABLED=true

# MiniMax
MINIMAX_API_KEY=your-key
MINIMAX_ENABLED=true
```

## 📈 性能优化

1. **并行处理**: asyncio 并行调用多个模型
2. **批量处理**: 支持批量评分提高吞吐量
3. **异步架构**: 全异步设计避免阻塞
4. **连接池**: HTTP 连接复用

## 🔒 一致性保障

1. **多次采样**: 每模型多次采样取平均
2. **多模型投票**: 多模型独立评分
3. **置信度校准**: 自动检测低置信度
4. **边界检测**: 极端分数预警

## 📝 与原版对比

| 功能 | 原版 (国外模型) | 此版本 (国产模型) |
|------|----------------|------------------|
| 主力模型 | GPT-4o | 通义千问 Qwen |
| 辅助模型 | Claude-3 | 智谱 GLM |
| 校验模型 | Gemini-Pro | MiniMax |
| 备用模型 | - | 文心一言/讯飞星火 |
| 聚合策略 | ✅ | ✅ |
| 置信度校准 | ✅ | ✅ |
| 批量测试 | ✅ | ✅ |
| Web 界面 | ✅ | ✅ |

## 🎯 使用场景

1. **教育考试**: 简答题自动评分
2. **竞赛评分**: 主观题评分
3. **作业批改**: 批量作业评分
4. **质量评估**: 答案质量评估

## 📄 许可证

MIT License

---

**版本**: v2.0.0  
**创建日期**: 2026-04-02  
**开发完成**: ✅ 全部功能已实现
