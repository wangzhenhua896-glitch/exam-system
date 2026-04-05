# AI 智能评分系统 v2.0

> 基于国产大模型的简答题自动化评分系统

## 📋 项目简介

本系统利用国产大语言模型对简答题进行自动化、高精度评分，重点消除模型输出的随机性，保障评分的一致性与可靠性。

**目标性能**：10 分钟内完成 1000 份试卷批改

## 🤖 支持的国产大模型

| 模型 | 提供商 | 状态 |
|------|--------|------|
| 通义千问 (Qwen) | 阿里云 | ✅ 主力 |
| 智谱 GLM | 智谱 AI | ✅ 主力 |
| MiniMax | MiniMax | ✅ 主力 |
| 文心一言 (ERNIE) | 百度 | ⚙️ 可选 |
| 讯飞星火 | 科大讯飞 | ⚙️ 可选 |

## ✨ 核心功能

### 1. 多模型集成投票
- 支持多个国产大模型独立评分
- 聚合结果提高准确性

### 2. 多次采样与聚合策略
- 可配置 1/3/5/7 次采样
- 支持多数投票、加权平均、置信度加权等策略

### 3. 置信度校准与边界检测
- 低/中/高置信度阈值（0.6/0.7/0.8）
- 低于阈值自动触发复核
- 对满分、零分等极端分数自动预警

### 4. 单题与批量评分
- 单题快速评分
- 批量性能测试面板
- 实时显示进度和一致性指标

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 3. 启动系统

```bash
python main.py
```

### 4. 访问界面

打开浏览器访问：http://localhost:5000

## 📁 项目结构

```
ai-grading-system/
├── app/
│   ├── __init__.py
│   ├── app.py                 # Flask 应用
│   ├── routes.py              # API 路由
│   ├── batch_routes.py        # 批量评分路由
│   ├── engine.py              # 聚合引擎
│   └── models/
│       ├── __init__.py
│       ├── base.py            # 基础模型接口
│       ├── qwen.py            # 通义千问
│       ├── glm.py             # 智谱 GLM
│       ├── minimax.py         # MiniMax
│       ├── ernie.py           # 百度文心
│       └── registry.py        # 模型注册表
├── config/
│   └── settings.py            # 配置文件
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   └── index.html
├── main.py                    # 主入口
├── requirements.txt
└── .env.example
```

## 🔧 配置说明

### 模型配置

在 `.env` 文件中配置各模型的 API Key：

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

### 评分策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 置信度加权 | 根据模型置信度加权平均 | 默认推荐 |
| 加权平均 | 简单加权平均 | 快速评分 |
| 多数投票 | 离散化后投票 | 高一致性要求 |

### 置信度阈值

- **低 (0.6)**: 低于此值必须人工复核
- **中 (0.7)**: 建议复核
- **高 (0.8)**: 可自动通过

## 📊 API 文档

### 单题评分

```bash
POST /api/grading/single

{
    "question": "题目内容",
    "answer": "学生答案",
    "max_score": 10,
    "sample_count": 3,
    "strategy": "confidence_weighted",
    "rubric": {}
}
```

### 批量测试

```bash
POST /api/batch/test

{
    "count": 100,
    "sample_count": 3,
    "strategy": "confidence_weighted",
    "rubric": {},
    "max_score": 10
}
```

### 列出模型

```bash
GET /api/grading/models
```

## 🎯 性能优化

1. **并行处理**: 多模型调用并行执行
2. **批量处理**: 支持批量评分提高吞吐量
3. **缓存机制**: 相似答案可缓存结果
4. **异步处理**: 使用 asyncio 提高并发性能

## 🔒 一致性保障

1. **多次采样**: 每个模型多次采样取平均
2. **多模型投票**: 多个模型独立评分后聚合
3. **置信度校准**: 自动检测低置信度结果
4. **边界检测**: 极端分数自动预警

## 📝 使用示例

### 单题评分

1. 在"单题评分"页面输入题目和学生答案
2. 设置满分、采样次数和聚合策略
3. 点击"开始评分"
4. 查看评分结果和各模型详细评分

### 批量测试

1. 切换到"批量测试"页面
2. 选择测试题数（10-1000）
3. 点击"开始测试"
4. 查看性能统计和吞吐量

## 🛠️ 开发

### 添加新模型

1. 在 `app/models/` 下创建新模型文件
2. 继承 `BaseModelClient` 类
3. 实现 `generate` 和 `grade_answer` 方法
4. 在 `registry.py` 中注册

### 自定义聚合策略

在 `engine.py` 中添加新的聚合方法：

```python
def _custom_strategy(self, responses, max_score):
    # 实现自定义聚合逻辑
    pass
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**版本**: v2.0.0  
**更新日期**: 2026-04-02  
**开发团队**: AI Grading Team
