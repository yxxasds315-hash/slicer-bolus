#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"   # 项目根目录（scripts/ 的上一级）
SLICER="/Applications/Slicer.app/Contents/MacOS/Slicer"

cleanup() {
  echo ""
  echo "=== 关闭所有服务 ==="
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "已关闭"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "=== 启动 Flask 后端 ==="
if lsof -ti:8765 > /dev/null 2>&1; then
  echo "Flask 后端已在运行 (端口 8765)"
  BACKEND_PID=$(lsof -ti:8765)
else
  python3 "${PROJECT_DIR}/backend/server.py" &
  BACKEND_PID=$!
  sleep 2
  echo "Flask 后端 PID: $BACKEND_PID"
fi

echo "=== 启动前端 ==="
if lsof -ti:5173 > /dev/null 2>&1; then
  echo "前端已在运行 (端口 5173)"
else
  cd "${PROJECT_DIR}/frontend" && npm run dev &
  FRONTEND_PID=$!
  sleep 2
  echo "前端 PID: $FRONTEND_PID"
fi

echo "=== 启动 Slicer ==="
"$SLICER" --python-script "${PROJECT_DIR}/backend/slicer_watcher.py" &
SLICER_PID=$!

sleep 3
open "http://localhost:5173"

echo ""
echo "=== Bolus Designer 已启动 ==="
echo "  前端: http://localhost:5173"
echo "  后端: http://localhost:8765"
echo "  停止: Ctrl+C"
echo "=========================="

wait $SLICER_PID
