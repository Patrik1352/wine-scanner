#!/usr/bin/env python3
"""Export a reference bundle from the research workspace (wine-photo-dataset) into artifacts/.

Takes the already computed index vectors (ensemble_ref_{tag}_v4.npz), copies every indexed reference
photo as photos/<slug><ext>, adds the catalog cards, equivalence groups, tie-break card texts and
recomputes 'twins' (catalog cards whose reference photos are byte-identical). Writes manifest.json with
sha256 of every file.

Example:
  python scripts/build_bundle.py --version v4 --out artifacts/reference_bundle
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from wine_scanner.bundle import sha256  # noqa: E402

WPD = "/home/jovyan/egor_bykov/wine-photo-dataset"
ap = argparse.ArgumentParser()
ap.add_argument("--version", default="v4")
ap.add_argument("--out", default=str(REPO / "artifacts/reference_bundle"))
ap.add_argument("--index-prefix", default=f"{WPD}/retrieval_experiment/ensemble_ref_{{tag}}_v4.npz")
ap.add_argument("--case-csv", default=f"{WPD}/strapi_output0709.csv")
ap.add_argument("--site-wines", default=f"{WPD}/data/site_wines_2026-09-23.jsonl")
ap.add_argument("--catalog", default="/home/jovyan/egor_bykov/wine-recognition/data/catalog_v1/catalog.jsonl")
ap.add_argument("--equivalence", default=f"{WPD}/retrieval_experiment/slug_equivalence_v3.json")
args = ap.parse_args()

out = Path(args.out)
if out.exists():
    sys.exit(f"{out} already exists; remove it or pass another --out")
(out / "photos").mkdir(parents=True)
lock = json.loads((REPO / "models.lock.json").read_text(encoding="utf-8"))
tags = [e["tag"] for e in lock["embedders"]]

idx = {t: np.load(args.index_prefix.format(tag=t), allow_pickle=True) for t in tags}
slugs = idx[tags[0]]["slugs"].astype(str)
for t in tags:
    assert np.array_equal(idx[t]["slugs"].astype(str), slugs), f"slug order differs in {t}"
src = idx[tags[0]]["paths"].astype(str)

photos, digests = [], {}
for s, p in zip(slugs, src):
    rel = f"photos/{s}{Path(p).suffix.lower() or '.jpg'}"
    shutil.copyfile(p, out / rel)
    photos.append(rel)
    digests[s] = hashlib.md5((out / rel).read_bytes()).hexdigest()
for t in tags:
    np.savez(out / f"index_{t}.npz", slugs=slugs, vecs=idx[t]["vecs"].astype(np.float32), photos=np.array(photos))

by_digest = defaultdict(list)
for s, d in digests.items():
    by_digest[d].append(s)
twins = {s: sorted(x for x in g if x != s) for g in by_digest.values() if len(g) > 1 for s in g}
(out / "twins.json").write_text(json.dumps(twins, ensure_ascii=False, indent=1), encoding="utf-8")

site = {}
for line in open(args.site_wines, encoding="utf-8"):
    r = json.loads(line)
    site[r["slug"]] = r
info = {}
for r in csv.DictReader(open(args.case_csv, encoding="utf-8")):
    s = r["Slug"].strip()
    if s and s not in info:
        cat = (site.get(s, {}).get("category") or r["Категория"]).strip()
        info[s] = (f"{r['Название вина'].strip()} — {r['Винодельня'].strip()}; категория: {cat}; "
                   f"сорт: {r['Сорт винограда'].strip() or '—'}")
(out / "card_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")

shutil.copyfile(args.catalog, out / "catalog.jsonl")
eq = json.loads(Path(args.equivalence).read_text(encoding="utf-8"))
(out / "equivalence.json").write_text(json.dumps(eq, ensure_ascii=False), encoding="utf-8")

files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
manifest = {
    "version": args.version,
    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "embedders": {e["tag"]: {"repo_id": e["repo_id"], "revision": e["revision"], "image_size": e["image_size"],
                             "adapter_sha256": sha256(REPO / e["adapter"] / "adapter_model.safetensors")}
                  for e in lock["embedders"]},
    "counts": {"wines": len(slugs), "twin_groups": sum(len(g) > 1 for g in by_digest.values()),
               "catalog_cards": sum(1 for _ in open(out / "catalog.jsonl", encoding="utf-8"))},
    "sources": {"index": args.index_prefix, "case_csv": args.case_csv, "catalog": args.catalog, "equivalence": args.equivalence},
    "files": {f: sha256(out / f) for f in files},
}
(out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: manifest[k] for k in ("version", "counts")}, ensure_ascii=False))
