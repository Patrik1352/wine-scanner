#!/usr/bin/env bash
# Stop the API and vLLM started by run_api.sh / run_vllm.sh (whole process groups, by recorded PID only).
cd "$(dirname "$0")/.."
for name in api vllm; do
  f=logs/$name.pid
  [ -f "$f" ] || continue
  pid=$(cat "$f")
  if kill -0 "$pid" 2>/dev/null; then
    kill -- -"$pid" 2>/dev/null || kill "$pid"
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$pid" 2>/dev/null && kill -9 -- -"$pid" 2>/dev/null
    echo "$name stopped (pid $pid)"
  fi
  rm -f "$f"
done
