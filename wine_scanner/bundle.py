"""Reference bundle: reference photos + precomputed index + catalog, versioned by manifest.json.

Layout:
  manifest.json       version, embedder revisions, sha256 of every file
  photos/<slug>.<ext> one reference photo per catalog wine
  index_<tag>.npz     slugs, vecs (L2-normalised), photos (paths relative to the bundle)
  catalog.jsonl       wine cards for GET /v1/wines/{slug}
  equivalence.json    slug -> group id (different catalog cards of the same wine)
  twins.json          slug -> slugs whose reference photo is byte-identical (resolved by label-text tie-break)
  card_info.json      slug -> short text card used by the tie-break prompt
"""
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Bundle:
    def __init__(self, root: Path, tags, verify: bool = True):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        if verify:
            bad = [f for f, h in self.manifest["files"].items() if not (self.root / f).exists() or sha256(self.root / f) != h]
            if bad:
                raise ValueError(f"reference bundle integrity check failed for {len(bad)} files, e.g. {bad[:3]}")
        self.version = self.manifest["version"]
        self.index = {}
        slugs = None
        for tag in tags:
            d = np.load(self.root / f"index_{tag}.npz", allow_pickle=False)
            s = d["slugs"].astype(str)
            if slugs is None:
                slugs, photos = s, d["photos"].astype(str)
            elif not np.array_equal(slugs, s):
                raise ValueError(f"index_{tag}.npz slug order differs from the other indexes")
            v = d["vecs"].astype(np.float32)
            self.index[tag] = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-9, None)
        self.slugs = slugs
        self.photo = {s: self.root / p for s, p in zip(slugs, photos)}
        self.catalog = {}
        for line in (self.root / "catalog.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                self.catalog[r["slug"]] = r
        self.equivalence = json.loads((self.root / "equivalence.json").read_text(encoding="utf-8"))
        self.twins = json.loads((self.root / "twins.json").read_text(encoding="utf-8"))
        self.card_info = json.loads((self.root / "card_info.json").read_text(encoding="utf-8"))
        groups = {}
        for s, g in self.equivalence.items():
            groups.setdefault(g, []).append(s)
        self._groups = groups

    def equivalents(self, slug):
        g = self.equivalence.get(slug)
        return [s for s in self._groups.get(g, []) if s != slug] if g is not None else []

    def name(self, slug):
        return (self.catalog.get(slug) or {}).get("name") or slug
