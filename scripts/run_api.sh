#!/usr/bin/env bash
# Start the recognition API (FastAPI + 3 image encoders) in the background.
# Env: GPU (default 0), WS_HOST (127.0.0.1), WS_PORT (8080), PYTHON (python3), plus WS_* settings
#      from wine_scanner/config.py (WS_VLLM_URL defaults to http://127.0.0.1:8000).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
GPU=${GPU:-0}; WS_HOST=${WS_HOST:-127.0.0.1}; WS_PORT=${WS_PORT:-8080}; PY=${PYTHON:-python3}
if [ -f logs/api.pid ] && kill -0 "$(cat logs/api.pid)" 2>/dev/null; then echo "API already running (pid $(cat logs/api.pid))"; exit 0; fi

CUDA_VISIBLE_DEVICES=$GPU WS_DEVICE=cuda:0 setsid "$PY" -m uvicorn wine_scanner.main:app \
  --host "$WS_HOST" --port "$WS_PORT" --workers 1 > logs/api.log 2>&1 < /dev/null &
echo $! > logs/api.pid
echo "API starting (pid $!, http://$WS_HOST:$WS_PORT); log: logs/api.log"
for _ in $(seq 1 120); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$WS_PORT/health/ready" || true)
  [ "$code" = "200" ] && { echo "API ready"; exit 0; }
  kill -0 "$(cat logs/api.pid)" 2>/dev/null || { echo "API exited, see logs/api.log"; tail -20 logs/api.log; exit 1; }
  sleep 5
done
echo "API not ready after 10 min: $(curl -s http://127.0.0.1:$WS_PORT/health/ready)"; exit 1
