#!/usr/bin/env python3
"""Download the pinned base models from Hugging Face into the HF cache (HF_HOME).
After that the service can run with HF_HUB_OFFLINE=1.
  python scripts/download_models.py            # encoders + verifier base model
  python scripts/download_models.py --no-verifier
"""
import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--no-verifier", action="store_true", help="skip the verifier base model (~9 GB)")
args = ap.parse_args()

lock = json.loads((REPO / "models.lock.json").read_text(encoding="utf-8"))
items = [(e["repo_id"], e["revision"], ["config.json", "preprocessor_config.json", "*.safetensors", "*.json"])
         for e in lock["embedders"]]
if not args.no_verifier:
    items.append((lock["verifier"]["repo_id"], lock["verifier"]["revision"], None))
for repo_id, revision, patterns in items:
    path = snapshot_download(repo_id, revision=revision, allow_patterns=patterns)
    print(f"{repo_id}@{revision[:10]} -> {path}")
