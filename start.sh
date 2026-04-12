#!/bin/bash
# AI 智能评分系统 - 本地启动脚本
# 用法: ./start.sh                    # 启动服务 (默认端口 5001)
#       PORT=5002 ./start.sh start    # 指定端口启动
#       ./start.sh stop               # 停止服务
#       ./start.sh restart            # 重启服务
#       ./start.sh status             # 查看状态

set -e

PORT="${PORT:-5001}"
PID_FILE="app-${PORT}.pid"
LOG_FILE="app-${PORT}.log"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

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
        echo "停止服务 (PID: $pid, 端口: ${PORT})..."
        kill "$pid" 2>/dev/null
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
        # 按端口定位残留进程
        if lsof -ti:${PORT} > /dev/null 2>&1; then
            echo "端口 ${PORT} 有残留进程，清理中..."
            lsof -ti:${PORT} | xargs kill 2>/dev/null || true
            sleep 1
            echo "已清理"
        else
            echo "服务未运行 (端口: ${PORT})"
        fi
    fi
    rm -f "$PID_FILE"
}

start_service() {
    if is_running; then
        echo "服务已在运行 (PID: $(get_pid), 端口: ${PORT})"
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
    echo "启动服务 (端口: ${PORT})..."
    cd "${APP_DIR}"
    nohup python main.py --port "${PORT}" --no-debug > "${LOG_FILE}" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2

    if is_running; then
        echo ""
        echo "========================================="
        echo "  服务已启动"
        echo "  访问: http://localhost:${PORT}"
        echo "  日志: tail -f ${LOG_FILE}"
        echo "========================================="
    else
        echo "启动失败，请查看 ${LOG_FILE}"
        exit 1
    fi
}

show_status() {
    if is_running; then
        echo "服务运行中 (PID: $(get_pid), 端口: ${PORT})"
        echo "访问: http://localhost:${PORT}"
    else
        echo "服务未运行 (端口: ${PORT})"
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
        echo "环境变量: PORT=<端口号> (默认 5001)"
        exit 1
        ;;
esac
