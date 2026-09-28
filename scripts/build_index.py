#!/usr/bin/env python3
"""Update a reference bundle after its photos changed.

Put/replace/delete files in <bundle>/photos/<slug>.<ext>, then run:
  python scripts/build_index.py --bundle artifacts/reference_bundle --version v5
Only photos whose sha256 differs from manifest.json are re-embedded (use --full to redo everything).
Twins and the manifest are recomputed. Needs a GPU (or --device cpu, slow).
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from wine_scanner.bundle import sha256  # noqa: E402
from wine_scanner.embedder import Embedder  # noqa: E402
from wine_scanner.images import to_rgb  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--bundle", default=str(REPO / "artifacts/reference_bundle"))
ap.add_argument("--version", required=True)
ap.add_argument("--device", default="cuda:0")
ap.add_argument("--full", action="store_true")
ap.add_argument("--batch", type=int, default=16)
args = ap.parse_args()

B = Path(args.bundle)
manifest = json.loads((B / "manifest.json").read_text(encoding="utf-8"))
known = manifest["files"]
photos = {p.stem: p for p in sorted((B / "photos").iterdir()) if p.is_file() and not p.name.startswith(".")}
emb = Embedder(REPO / "models.lock.json", args.device)
old = {t: np.load(B / f"index_{t}.npz", allow_pickle=False) for t in emb.tags}
old_row = {s: i for i, s in enumerate(old[emb.tags[0]]["slugs"].astype(str))}

todo = [s for s, p in photos.items() if args.full or s not in old_row
        or known.get(str(p.relative_to(B))) != sha256(p)]
removed = sorted(set(old_row) - set(photos))
print(f"photos: {len(photos)} | re-embed: {len(todo)} | removed: {len(removed)}", flush=True)

new_vecs = {t: {} for t in emb.tags}
for i in range(0, len(todo), args.batch):
    chunk = todo[i:i + args.batch]
    v = emb.encode([to_rgb(Image.open(photos[s])) for s in chunk])
    for t in emb.tags:
        for s, x in zip(chunk, v[t]):
            new_vecs[t][s] = x

slugs = sorted(photos)
rel = np.array([str(photos[s].relative_to(B)) for s in slugs])
for t in emb.tags:
    vecs = np.stack([new_vecs[t][s] if s in new_vecs[t] else old[t]["vecs"][old_row[s]] for s in slugs]).astype(np.float32)
    np.savez(B / f"index_{t}.npz", slugs=np.array(slugs), vecs=vecs, photos=rel)

by_digest = defaultdict(list)
for s in slugs:
    by_digest[hashlib.md5(photos[s].read_bytes()).hexdigest()].append(s)
twins = {s: sorted(x for x in g if x != s) for g in by_digest.values() if len(g) > 1 for s in g}
(B / "twins.json").write_text(json.dumps(twins, ensure_ascii=False, indent=1), encoding="utf-8")

manifest["version"] = args.version
manifest["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
manifest["counts"]["wines"] = len(slugs)
manifest["counts"]["twin_groups"] = sum(len(g) > 1 for g in by_digest.values())
manifest["files"] = {str(p.relative_to(B)): sha256(p) for p in sorted(B.rglob("*"))
                     if p.is_file() and p.name != "manifest.json"}
(B / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"bundle {args.version}: {len(slugs)} wines, {manifest['counts']['twin_groups']} twin groups")
