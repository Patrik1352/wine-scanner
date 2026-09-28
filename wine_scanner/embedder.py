"""Three SigLIP/SigLIP2 so400m image encoders with LoRA adapters merged in; score = mean cosine."""
import json
import threading
from pathlib import Path

import numpy as np
import torch
from peft import PeftModel
from torchvision import transforms
from transformers import SiglipVisionModel

from .config import REPO_ROOT


def load_lock(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Embedder:
    def __init__(self, models_lock, device="cuda:0"):
        self.device = device
        self.specs = load_lock(models_lock)["embedders"]
        self.tags = [s["tag"] for s in self.specs]
        self.models, self.transforms = {}, {}
        for s in self.specs:
            base = SiglipVisionModel.from_pretrained(s["repo_id"], revision=s["revision"], torch_dtype=torch.bfloat16)
            model = PeftModel.from_pretrained(base, str(REPO_ROOT / s["adapter"])).merge_and_unload()
            self.models[s["tag"]] = model.to(device).eval()
            size = s["image_size"]
            # square resize without keeping aspect ratio: this is how the adapters were trained
            self.transforms[s["tag"]] = transforms.Compose([
                transforms.Resize((size, size)), transforms.ToTensor(), transforms.Normalize([0.5] * 3, [0.5] * 3)])
        self._lock = threading.Lock()

    @torch.no_grad()
    def encode(self, images):
        """list of RGB PIL images -> {tag: (n, dim) L2-normalised float32}"""
        out = {}
        with self._lock:
            for tag, model in self.models.items():
                x = torch.stack([self.transforms[tag](im) for im in images]).to(self.device, dtype=torch.bfloat16)
                v = model(pixel_values=x).pooler_output.float()
                out[tag] = torch.nn.functional.normalize(v, dim=-1).cpu().numpy()
        return out

    def similarity(self, image, index):
        """cosine similarity of one image to every reference, averaged over the encoders"""
        q = self.encode([image])
        return sum(q[t][0] @ index[t].T for t in self.tags) / len(self.tags)


def top_k(sim: np.ndarray, k: int):
    idx = np.argpartition(-sim, k)[:k]
    return idx[np.argsort(-sim[idx])]
