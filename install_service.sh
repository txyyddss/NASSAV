#!/bin/bash
# TX媒体库AV求片 - Debian/Ubuntu systemd 服务安装脚本
# 用法:
#   sudo bash install_service.sh install    # 安装并启动服务
#   sudo bash install_service.sh uninstall  # 卸载服务

set -e

SERVICE_NAME="nassav-webui"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# 自动检测路径
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3 2>/dev/null || echo '/usr/bin/python3')"
RUN_USER="${SUDO_USER:-$(whoami)}"

install_service() {
    echo "=== 安装 ${SERVICE_NAME} 系统服务 ==="

    # 检查 python3
    if [ ! -x "$PYTHON_BIN" ]; then
        echo "错误: 未找到 python3，请先安装 Python 3.11+"
        exit 1
    fi

    # 检查 main.py
    if [ ! -f "${PROJECT_DIR}/main.py" ]; then
        echo "错误: 未找到 main.py，请在项目根目录下运行此脚本"
        exit 1
    fi

    echo "项目目录: ${PROJECT_DIR}"
    echo "Python路径: ${PYTHON_BIN}"
    echo "运行用户: ${RUN_USER}"

    # 创建 systemd unit 文件
    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=TX媒体库AV求片 WebUI Service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_BIN} ${PROJECT_DIR}/main.py --webui
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # 重载并启动
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"

    echo ""
    echo "=== 安装完成 ==="
    echo "服务状态: systemctl status ${SERVICE_NAME}"
    echo "查看日志: journalctl -u ${SERVICE_NAME} -f"
    echo "停止服务: sudo systemctl stop ${SERVICE_NAME}"
    echo "重启服务: sudo systemctl restart ${SERVICE_NAME}"
}

uninstall_service() {
    echo "=== 卸载 ${SERVICE_NAME} 系统服务 ==="

    if [ -f "${SERVICE_FILE}" ]; then
        systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
        systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
        echo "服务已卸载"
    else
        echo "服务未安装，无需卸载"
    fi
}

# 主入口
case "${1}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    *)
        echo "用法: sudo bash $0 {install|uninstall}"
        exit 1
        ;;
esac
