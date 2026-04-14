#!/bin/bash
# AI 智能评分系统 - 部署脚本
# 用法: ./deploy.sh                          # 部署到默认服务器
#       ./deploy.sh 192.168.1.100            # 部署到指定服务器
#       ./deploy.sh 192.168.1.100 -p 5002    # 部署到指定端口
#       ./deploy.sh 192.168.1.100 -d /opt/ai-grading-v2  # 部署到指定目录
#       ./deploy.sh 192.168.1.100 -p 5002 -d /opt/ai-grading-v2  # 完整指定

set -e

# 默认值
DEFAULT_HOST="123.56.117.123"
DEFAULT_PORT=5001
DEFAULT_DIR="/opt/ai-grading"

REMOTE_USER="root"
REMOTE_PASS="Wzh13901143779!"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# 解析参数
REMOTE_HOST="${DEFAULT_HOST}"
REMOTE_PORT="${DEFAULT_PORT}"
REMOTE_DIR="${DEFAULT_DIR}"

args=("$@")
idx=0
while [ $idx -lt ${#args[@]} ]; do
    case "${args[$idx]}" in
        -p|--port)
            idx=$((idx+1))
            REMOTE_PORT="${args[$idx]}"
            ;;
        -d|--dir)
            idx=$((idx+1))
            REMOTE_DIR="${args[$idx]}"
            ;;
        -h|--help)
            echo "用法: $0 [主机] [选项]"
            echo ""
            echo "选项:"
            echo "  主机          目标服务器 IP (默认: ${DEFAULT_HOST})"
            echo "  -p, --port    服务端口 (默认: ${DEFAULT_PORT})"
            echo "  -d, --dir     远程目录 (默认: ${DEFAULT_DIR})"
            echo ""
            echo "示例:"
            echo "  $0                              # 默认服务器:5001"
            echo "  $0 192.168.1.100                # 指定服务器"
            echo "  $0 192.168.1.100 -p 5002        # 指定端口"
            echo "  $0 192.168.1.100 -d /opt/v2     # 指定目录"
            echo "  $0 192.168.1.100 -p 5002 -d /opt/v2  # 全指定"
            exit 0
            ;;
        *)
            if [ "$REMOTE_HOST" = "$DEFAULT_HOST" ]; then
                REMOTE_HOST="${args[$idx]}"
            fi
            ;;
    esac
    idx=$((idx+1))
done

# sshpass 封装函数
remote() {
    sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

echo "========================================="
echo " AI 智能评分系统 - 部署"
echo "========================================="
echo ""
echo "  目标: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
echo "  端口: ${REMOTE_PORT}"
echo ""

# 1. 同步文件
echo "[1/4] 同步文件..."
remote "mkdir -p ${REMOTE_DIR}"

cd "$LOCAL_DIR"
tar czf - \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='.env' \
    --exclude='.git' \
    --exclude='.claude' \
    --exclude='data' \
    --exclude='exports' \
    --exclude='logs' \
    --exclude='results' \
    --exclude='consistency_test' \
    --exclude='tests' \
    --exclude='node_modules' \
    --exclude='*.db' \
    app/ config/ dist/ templates/ static/ main.py requirements.txt start.sh .env.example \
    | sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        "cd ${REMOTE_DIR} && tar xzf -"

echo ""

# 2. 远程安装依赖
echo "[2/4] 安装依赖..."
remote "cd ${REMOTE_DIR} && /usr/bin/python3.11 -m pip install -q -r requirements.txt 2>&1 | tail -3"

echo ""

# 3. 停止旧进程（按目录+端口定位，不误杀其他实例）
echo "[3/4] 停止旧进程..."
remote "cd ${REMOTE_DIR} && \
    PID_FILE='app-${REMOTE_PORT}.pid' && \
    if [ -f \"\$PID_FILE\" ]; then \
        OLD_PID=\$(cat \"\$PID_FILE\"); \
        kill \"\$OLD_PID\" 2>/dev/null || true; \
        sleep 1; \
        kill -9 \"\$OLD_PID\" 2>/dev/null || true; \
        rm -f \"\$PID_FILE\"; \
    fi; \
    # 兜底：按端口杀进程
    fuser -k ${REMOTE_PORT}/tcp 2>/dev/null || true"

echo ""

# 4. 启动服务
echo "[4/4] 启动服务..."
remote "cd ${REMOTE_DIR} && \
    mkdir -p logs && \
    PORT=${REMOTE_PORT} FLASK_DEBUG=false nohup /usr/bin/python3.11 main.py --port ${REMOTE_PORT} --no-debug \
    > app-${REMOTE_PORT}.log 2>&1 & \
    echo \$! > app-${REMOTE_PORT}.pid"

# 等待启动
sleep 3

# 健康检查
echo ""
echo "健康检查..."
if remote "curl -sf http://localhost:${REMOTE_PORT}/ > /dev/null 2>&1"; then
    echo ""
    echo "========================================="
    echo " 部署成功!"
    echo " 访问: http://${REMOTE_HOST}:${REMOTE_PORT}"
    echo "========================================="
else
    echo ""
    echo "========================================="
    echo " ⚠️  服务已启动但健康检查未通过"
    echo " 查看日志: ssh ${REMOTE_USER}@${REMOTE_HOST} 'tail -20 ${REMOTE_DIR}/app-${REMOTE_PORT}.log'"
    echo "========================================="
fi
