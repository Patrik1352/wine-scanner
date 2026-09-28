import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import settings
from .images import ImageError, decode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("wine_scanner")

state = {"recognizer": None, "error": None}


def _load():
    try:
        from .pipeline import Recognizer
        r = Recognizer(settings)
        state["recognizer"] = r
        log.info("models and reference bundle %s loaded (%d wines)", r.bundle.version, len(r.bundle.slugs))
        if settings.warm_refs:
            r.warm_refs()
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {e}"
        log.exception("startup failed")


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_load, daemon=True).start()
    yield


app = FastAPI(title="Wine label scanner", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


def _recognizer():
    r = state["recognizer"]
    if r is None:
        raise HTTPException(503, state["error"] or "models are loading")
    return r


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    r = _recognizer()
    problems = []
    if settings.warm_refs and not r.refs_warm:
        problems.append("reference cache is warming up")
    if not r.verifier.ready():
        problems.append(f"verifier is not reachable at {settings.vllm_url}")
    if problems:
        raise HTTPException(503, "; ".join(problems))
    return {"status": "ready", "reference_bundle": r.bundle.version, "wines": len(r.bundle.slugs)}


async def _run(image: UploadFile):
    r = _recognizer()
    data = await image.read(settings.max_bytes + 1)
    try:
        im = await run_in_threadpool(decode, data, settings.max_bytes, settings.max_pixels)
    except ImageError as e:
        raise HTTPException(e.status, str(e))
    return r, await run_in_threadpool(r.recognize, im)


@app.post("/v1/eval/predict")
async def eval_predict(image: UploadFile = File(...)):
    """Organizers' format: ranked list, element [0] is the answer."""
    _, res = await _run(image)
    return [{"slug": c["slug"], "score": c["score"], "p_yes": c["p_yes"], "cosine": c["cosine"]} for c in res["candidates"]]


@app.post("/v1/recognize")
async def recognize(image: UploadFile = File(...)):
    """Frontend contract (frontend/API_CONTRACT.md). Every photo is a catalog wine by the case rules,
    so the status is always `matched`; uncertainty is reported via `confidence` / `low_confidence`."""
    r, res = await _run(image)
    return {
        "status": "matched",
        "slug": res["slug"],
        "confidence": res["confidence"],
        "confidence_kind": "verifier_p_yes",
        "low_confidence": res["low_confidence"],
        "alternatives": r.bundle.equivalents(res["slug"]),
        "top_k": res["candidates"],
        "tiebreak": res["tiebreak"],
        "degraded": res["degraded"],
        "timings_ms": res["timings_ms"],
        "reference_bundle": r.bundle.version,
    }


def _safe_url(u):
    return u if isinstance(u, str) and u.startswith(("http://", "https://")) else None


@app.get("/v1/wines/{slug}")
def wine(slug: str):
    rec = _recognizer().bundle.catalog.get(slug)
    if rec is None:
        raise HTTPException(404, "wine not found")
    return {
        "slug": rec["slug"], "name": rec.get("name"), "winery_name": rec.get("winery_name"), "region": rec.get("region"),
        "category": rec.get("category"), "color_category": rec.get("color_category"),
        "sweetness_from_category": rec.get("sweetness_from_category"), "grapes": rec.get("grapes") or [],
        "description": rec.get("description"), "alcohol_percent": rec.get("alcohol_percent"),
        "alcohol_max_percent": rec.get("alcohol_max_percent"), "serving_temperature_c": rec.get("serving_temperature_c"),
        "food_pairings": rec.get("food_pairings") or [], "public_rating": rec.get("public_rating"),
        "guide_rating": rec.get("guide_rating"), "image_url": _safe_url(rec.get("image_url")),
        "source_url": _safe_url(rec.get("source_url")), "fetched_at": rec.get("fetched_at"),
        "similar_wine_slugs": rec.get("similar_wine_slugs") or [],
    }
