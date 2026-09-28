#!/usr/bin/env python3
"""Evaluate a running service on labelled photos laid out as <dir>/<gold_slug>/<photo>.
Requests are sequential, like the organizers' participant_test.sh.
  python scripts/evaluate.py --data /path/to/photos_by_slug [--endpoint http://127.0.0.1:8080/v1/eval/predict]
Accuracy is reported strict (exact slug) and lenient (equivalent catalog cards count as correct).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import requests

REPO = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/eval/predict")
ap.add_argument("--bundle", default=str(REPO / "artifacts/reference_bundle"))
ap.add_argument("--out", default=None, help="write per-photo results as jsonl")
args = ap.parse_args()

eq = json.loads((Path(args.bundle) / "equivalence.json").read_text(encoding="utf-8"))
same = lambda a, b: a == b or (a in eq and b in eq and eq[a] == eq[b])
exts = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tif", ".tiff"}
items = [(p, p.parent.name) for p in sorted(Path(args.data).rglob("*"))
         if p.is_file() and p.suffix.lower() in exts and not p.name.startswith(".")]
if not items:
    sys.exit("no photos found")
rows = []
for p, gold in items:
    t0 = time.time()
    try:
        r = requests.post(args.endpoint, files={"image": (p.name, p.read_bytes())}, timeout=10)
        cands = [c["slug"] for c in r.json()] if r.ok else []
    except (requests.RequestException, ValueError):
        cands = []
    rows.append({"path": str(p), "gold": gold, "pred": cands[0] if cands else None, "top5": cands,
                 "latency_ms": round((time.time() - t0) * 1000)})
n = len(rows)
lat = [r["latency_ms"] for r in rows]
print(f"photos: {n}")
print(f"top-1 strict:  {np.mean([r['pred'] == r['gold'] for r in rows]):.3f}")
print(f"top-1 lenient: {np.mean([r['pred'] is not None and same(r['pred'], r['gold']) for r in rows]):.3f}")
print(f"top-5 lenient: {np.mean([any(same(c, r['gold']) for c in r['top5']) for r in rows]):.3f}")
print(f"no answer:     {sum(r['pred'] is None for r in rows)}")
print(f"latency ms: median {np.median(lat):.0f}, p90 {np.percentile(lat, 90):.0f}, max {max(lat)}")
if args.out:
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
