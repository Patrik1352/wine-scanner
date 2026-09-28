#!/usr/bin/env bash
# Start the verifier: vLLM with Qwen3.5-4B (served as `base`) + LoRA (served as `sft`), in the background.
# Env: GPU (default 0), VLLM_PORT (8000), VLLM_BIN (vllm), VLLM_GPU_UTIL (0.3 ~= 25 GB on A100-80),
#      VERIFIER_BASE (default: repo id from models.lock.json; may be a local directory).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
GPU=${GPU:-0}; VLLM_PORT=${VLLM_PORT:-8000}; VLLM_BIN=${VLLM_BIN:-vllm}; VLLM_GPU_UTIL=${VLLM_GPU_UTIL:-0.3}
PY=${PYTHON:-python3}
read -r LOCK_REPO LOCK_REV < <($PY -c 'import json;v=json.load(open("models.lock.json"))["verifier"];print(v["repo_id"],v["revision"])')
BASE=${VERIFIER_BASE:-$LOCK_REPO}
REV_ARGS=(); [ "$BASE" = "$LOCK_REPO" ] && REV_ARGS=(--revision "$LOCK_REV")
[ -f artifacts/verifier_lora/adapter_model.safetensors ] || { echo "missing artifacts/verifier_lora (see README)"; exit 1; }
if [ -f logs/vllm.pid ] && kill -0 "$(cat logs/vllm.pid)" 2>/dev/null; then echo "vLLM already running (pid $(cat logs/vllm.pid))"; exit 0; fi

CUDA_VISIBLE_DEVICES=$GPU setsid "$VLLM_BIN" serve "$BASE" "${REV_ARGS[@]}" --served-model-name base --dtype bfloat16 \
  --host 127.0.0.1 --port "$VLLM_PORT" --gpu-memory-utilization "$VLLM_GPU_UTIL" \
  --max-model-len 16384 --max-num-seqs 32 --max-num-batched-tokens 16384 --enable-prefix-caching \
  --limit-mm-per-prompt '{"image": 2, "video": 0}' --mm-processor-kwargs '{"max_pixels": 1003520}' \
  --enable-lora --lora-modules sft=artifacts/verifier_lora --max-lora-rank 16 \
  > logs/vllm.log 2>&1 < /dev/null &
echo $! > logs/vllm.pid
echo "vLLM starting (pid $!, port $VLLM_PORT, GPU $GPU); log: logs/vllm.log"
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$VLLM_PORT/v1/models" | grep -q '"sft"' && { echo "vLLM ready"; exit 0; }
  kill -0 "$(cat logs/vllm.pid)" 2>/dev/null || { echo "vLLM exited, see logs/vllm.log"; tail -20 logs/vllm.log; exit 1; }
  sleep 5
done
echo "vLLM not ready after 10 min, see logs/vllm.log"; exit 1
