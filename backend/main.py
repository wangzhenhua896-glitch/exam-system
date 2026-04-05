#!/usr/bin/env python3
"""
考试系统后端入口
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, exams, questions, users, submissions
from app.core.config import settings
from app.core.database import engine, Base

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Exam System API",
    description="在线考试系统后端 API",
    version="0.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/users", tags=["用户"])
app.include_router(exams.router, prefix="/api/exams", tags=["考试"])
app.include_router(questions.router, prefix="/api/questions", tags=["题目"])
app.include_router(submissions.router, prefix="/api/submissions", tags=["答题"])


@app.get("/")
async def root():
    return {"message": "Welcome to Exam System API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
