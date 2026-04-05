# Exam System - 全栈在线考试系统

一个基于 FastAPI + Vue3 的全栈在线考试系统，支持多种题型、自动评分、成绩统计等功能。

## 技术栈

### 后端
- **FastAPI** - 高性能 Python Web 框架
- **SQLAlchemy** - ORM 数据库操作
- **SQLite/PostgreSQL** - 数据库
- **JWT** - 用户认证
- **Pydantic** - 数据验证

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **Element Plus** - UI 组件库
- **Vue Router** - 路由管理
- **Pinia** - 状态管理
- **Axios** - HTTP 客户端

## 项目结构

```
exam-system/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # 测试代码
│   ├── requirements.txt    # Python 依赖
│   └── main.py             # 入口文件
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/            # API 接口
│   │   ├── components/     # 组件
│   │   ├── views/          # 页面
│   │   ├── router/         # 路由
│   │   ├── store/          # 状态管理
│   │   └── utils/          # 工具函数
│   ├── package.json
│   └── vite.config.js
└── docs/                   # 文档
```

## 功能特性

- [x] 用户管理（学生、教师、管理员）
- [x] 题库管理（单选、多选、判断、填空、简答）
- [x] 考试管理（创建考试、时间控制、防作弊）
- [x] 自动评分（客观题自动评分，主观题 AI 辅助评分）
- [x] 成绩统计（个人成绩、班级排名、错题分析）
- [x] 试卷导出（PDF、Word 格式）

## 快速开始

### 后端启动

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

## API 文档

启动后端后访问：http://localhost:8000/docs

## 贡献

欢迎提交 Issue 和 PR！

## 许可证

MIT License
