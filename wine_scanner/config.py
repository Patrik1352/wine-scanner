import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env(name, default):
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    bundle_dir: Path = field(default_factory=lambda: Path(_env("WS_BUNDLE_DIR", REPO_ROOT / "artifacts/reference_bundle")))
    models_lock: Path = field(default_factory=lambda: Path(_env("WS_MODELS_LOCK", REPO_ROOT / "models.lock.json")))
    device: str = field(default_factory=lambda: _env("WS_DEVICE", "cuda:0"))
    vllm_url: str = field(default_factory=lambda: _env("WS_VLLM_URL", "http://127.0.0.1:8000"))
    verifier_model: str = field(default_factory=lambda: _env("WS_VERIFIER_MODEL", "sft"))
    base_model: str = field(default_factory=lambda: _env("WS_BASE_MODEL", "base"))
    top_k: int = field(default_factory=lambda: int(_env("WS_TOP_K", "5")))
    # final score = FUSION_A * (cos - cos_max) / FUSION_T + P(YES)
    fusion_a: float = field(default_factory=lambda: float(_env("WS_FUSION_A", "0.25")))
    fusion_t: float = field(default_factory=lambda: float(_env("WS_FUSION_T", "0.05")))
    low_confidence: float = field(default_factory=lambda: float(_env("WS_LOW_CONFIDENCE", "0.3")))
    # images sent to the verifier are downscaled to this longest side (the LoRA was trained at ~1M px)
    image_side: int = field(default_factory=lambda: int(_env("WS_IMAGE_SIDE", "1600")))
    tiebreak: bool = field(default_factory=lambda: _env("WS_TIEBREAK", "1") == "1")
    # kosher card -> its regular counterpart (see wine_scanner/redirects.py)
    redirects: bool = field(default_factory=lambda: _env("WS_REDIRECTS", "1") == "1")
    warm_refs: bool = field(default_factory=lambda: _env("WS_WARM_REFS", "1") == "1")
    verify_bundle: bool = field(default_factory=lambda: _env("WS_VERIFY_BUNDLE", "1") == "1")
    max_bytes: int = field(default_factory=lambda: int(_env("WS_MAX_BYTES", str(25 * 1024 * 1024))))
    max_pixels: int = field(default_factory=lambda: int(_env("WS_MAX_PIXELS", "64000000")))
    verifier_timeout: float = field(default_factory=lambda: float(_env("WS_VERIFIER_TIMEOUT", "8")))
    cors_origins: str = field(default_factory=lambda: _env("WS_CORS_ORIGINS", "*"))


settings = Settings()
