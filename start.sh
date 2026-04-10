#!/bin/bash
# AI 智能评分系统 - 本地启动脚本
# 用法: ./start.sh          # 启动服务
#       ./start.sh stop     # 停止服务
#       ./start.sh restart  # 重启服务
#       ./start.sh status   # 查看状态

set -e

PID_FILE="app.pid"
PORT=5001

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

stop_service() {
    if is_running; then
        local pid=$(get_pid)
        echo "停止服务 (PID: $pid)..."
        kill "$pid" 2>/dev/null
        # 等待进程退出
        for i in $(seq 1 10); do
            if ! is_running; then
                break
            fi
            sleep 0.5
        done
        if is_running; then
            echo "进程未退出，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
        echo "服务已停止"
    else
        # 尝试清理残留进程
        if pgrep -f "python main.py" > /dev/null 2>&1; then
            echo "发现残留进程，清理中..."
            pkill -f "python main.py" 2>/dev/null || true
            sleep 1
            echo "已清理"
        else
            echo "服务未运行"
        fi
    fi
    rm -f "$PID_FILE"
}

start_service() {
    if is_running; then
        echo "服务已在运行 (PID: $(get_pid))"
        echo "访问: http://localhost:${PORT}"
        return 0
    fi

    # 检查端口占用
    if lsof -ti:${PORT} > /dev/null 2>&1; then
        echo "端口 ${PORT} 被占用，尝试清理..."
        lsof -ti:${PORT} | xargs kill 2>/dev/null || true
        sleep 1
    fi

    # 检查 .env
    if [ ! -f .env ]; then
        echo "未找到 .env 文件，从 .env.example 创建..."
        cp .env.example .env
        echo "已创建 .env，请编辑填入 API Key 后重新启动"
        exit 1
    fi

    # 安装依赖
    echo "检查依赖..."
    pip install -q -r requirements.txt 2>/dev/null

    # 创建日志目录
    mkdir -p logs

    # 启动
    echo "启动服务..."
    nohup python main.py > app.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2

    if is_running; then
        echo ""
        echo "========================================="
        echo "  服务已启动"
        echo "  访问: http://localhost:${PORT}"
        echo "  日志: tail -f app.log"
        echo "========================================="
    else
        echo "启动失败，请查看 app.log"
        exit 1
    fi
}

show_status() {
    if is_running; then
        echo "服务运行中 (PID: $(get_pid))"
        echo "访问: http://localhost:${PORT}"
    else
        echo "服务未运行"
    fi
}

# 主逻辑
case "${1:-start}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 1
        start_service
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
