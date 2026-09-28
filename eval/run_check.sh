#!/usr/bin/env bash
# Run the case holder's evaluation script (eval/case/participant_test.sh, unchanged) against the local
# service and print a summary: answer and response time for every image.
#
#   eval/run_check.sh --images-dir eval/case/queries --manifest eval/case/queries.tsv
#
# Extra arguments are passed to participant_test.sh. Defaults: --endpoint http://127.0.0.1:$WS_PORT/v1/eval/predict,
# --output eval/results/predictions_<timestamp>.jsonl. Requires bash, curl, jq, awk (the organizers' script).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${WS_PORT:-8080}
args=("$@")
[[ " $* " == *" --endpoint "* ]] || args+=(--endpoint "http://127.0.0.1:$PORT/v1/eval/predict")
if [[ " $* " != *" --output "* ]]; then
  mkdir -p eval/results
  out="eval/results/predictions_$(date +%Y%m%d_%H%M%S).jsonl"
  args+=(--output "$out")
else
  out=$(printf '%s\n' "$@" | awk 'f{print;exit} $0=="--output"{f=1}')
fi
endpoint=$(printf '%s\n' "${args[@]}" | awk 'f{print;exit} $0=="--endpoint"{f=1}')
base=${endpoint%/v1/*}

echo "waiting for $base/health/ready ..."
for _ in $(seq 1 120); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$base/health/ready" || true)" = "200" ] && break
  sleep 5
done
[ "$(curl -s -o /dev/null -w '%{http_code}' "$base/health/ready" || true)" = "200" ] || { echo "service is not ready"; exit 1; }

bash eval/case/participant_test.sh "${args[@]}"

python3 - "$out" << 'EOF'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
lat = sorted(r["latency_ms"] for r in rows)
q = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))]
print(f"{'query_id':<14}{'latency_ms':>11}  predicted_slug")
for r in rows:
    print(f"{r['query_id']:<14}{r['latency_ms']:>11}  {r['predicted_slug']}")
print(f"\nimages: {len(rows)} | no answer (null): {sum(r['predicted_slug'] is None for r in rows)}")
print(f"latency ms: median {q(0.5)}, p90 {q(0.9)}, max {lat[-1]} | > 3 s: {sum(x > 3000 for x in lat)} | >= 10 s (timeout): {sum(x >= 10000 for x in lat)}")
print(f"predictions: {sys.argv[1]}")
EOF
