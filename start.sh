#!/bin/bash
# AI Grading System - 快速启动脚本

echo "🚀 AI 智能评分系统 v2.0"
echo "========================"
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件"
    echo "📝 正在从 .env.example 创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件"
    echo "⚠️  请编辑 .env 文件填入你的 API Key"
    echo ""
    echo "   支持的国产模型："
    echo "   - 通义千问 (Qwen)"
    echo "   - 智谱 GLM"
    echo "   - MiniMax"
    echo "   - 百度文心 (可选)"
    echo ""
    read -p "按回车键继续..."
fi

# 安装依赖
echo "📦 检查依赖..."
pip install -q -r requirements.txt

# 启动应用
echo ""
echo "🚀 启动系统..."
echo "📍 访问地址：http://localhost:5000"
echo ""

python main.py
