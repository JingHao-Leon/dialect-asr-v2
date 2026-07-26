#!/bin/bash
# 一键启动方言语音识别系统 v2.0 (FastAPI + Fun-ASR 1.5)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  方言语音识别系统 v2.0"
echo "  FastAPI + 阿里云百炼 Fun-ASR 1.5"
echo "=========================================="

# 加载项目自带 key（解压即用）
if [[ -f "config/dialect_stt.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "config/dialect_stt.env"
    set +a
    echo "[key] 已加载 config/dialect_stt.env（项目自带）"
elif [[ -f ~/.config/dialect_stt.env ]]; then
    set -a
    source ~/.config/dialect_stt.env
    set +a
    echo "[key] 已加载 ~/.config/dialect_stt.env（用户级）"
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3"
    exit 1
fi

# 安装依赖
echo "[1/4] 安装 Python 依赖..."
pip3 install -q fastapi uvicorn python-multipart dashscope 2>&1 | tail -3

# 检查 ffmpeg
echo "[2/4] 检查 ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  未检测到 ffmpeg，请先安装："
    echo "    macOS:  brew install ffmpeg"
    echo "    Ubuntu: sudo apt install ffmpeg"
    read -p "继续启动？[y/N] " yn
    [[ $yn != [yY]* ]] && exit 1
fi

# 检查 API Key
echo "[3/4] 检查 DASHSCOPE_API_KEY..."
if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
    echo "❌ 未找到 API key"
    echo "    解压后请确认 config/dialect_stt.env 文件存在"
    exit 1
fi
echo "  key 前缀: ${DASHSCOPE_API_KEY:0:6}..."

# 启动
PORT=${PORT:-5001}
echo "[4/4] 启动 FastAPI 服务 (端口 $PORT)..."
echo ""
echo "  打开浏览器: http://127.0.0.1:$PORT"
echo "  API 文档:   http://127.0.0.1:$PORT/docs"
echo ""
exec python3 -m uvicorn app:app --host 0.0.0.0 --port $PORT
