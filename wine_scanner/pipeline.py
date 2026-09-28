"""photo -> ranked catalog candidates.

1. embeddings (3 encoders) -> cosine to every reference -> top-K
2. verifier P(YES) for each candidate (parallel requests to vLLM)
3. final score = A * (cos - cos_max) / T + P(YES); candidates ordered by it
4. if the winner has catalog twins with a byte-identical reference photo, the base model reads the label
   and picks among them
The first candidate is the answer. A slug is always returned: if the verifier is unavailable the
embedding ranking is used (degraded=True).
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from .bundle import Bundle
from .embedder import Embedder, top_k
from .images import jpeg_data_uri, to_rgb
from .verifier import Verifier

log = logging.getLogger("wine_scanner")


class Recognizer:
    def __init__(self, settings):
        self.s = settings
        self.embedder = Embedder(settings.models_lock, settings.device)
        self.bundle = Bundle(settings.bundle_dir, self.embedder.tags, verify=settings.verify_bundle)
        self.verifier = Verifier(settings.vllm_url, settings.verifier_model, settings.base_model, settings.verifier_timeout)
        self.pool = ThreadPoolExecutor(max_workers=4 * settings.top_k)
        self._ref_uri, self._ref_lock = {}, threading.Lock()
        self.refs_warm = False

    def ref_uri(self, slug):
        with self._ref_lock:
            u = self._ref_uri.get(slug)
        if u is None:
            u = jpeg_data_uri(to_rgb(Image.open(self.bundle.photo[slug])), self.s.image_side)
            with self._ref_lock:
                self._ref_uri[slug] = u
        return u

    def warm_refs(self):
        """Pre-encode every reference once: re-encoding 5 references per request costs ~0.45 s."""
        t0 = time.time()
        list(self.pool.map(self.ref_uri, self.bundle.slugs))
        self.refs_warm = True
        log.info("reference cache warm: %d photos in %.0fs", len(self.bundle.slugs), time.time() - t0)

    def recognize(self, image: Image.Image):
        t0 = time.time()
        sim = self.embedder.similarity(image, self.bundle.index)
        idx = top_k(sim, self.s.top_k)
        cands = [str(self.bundle.slugs[i]) for i in idx]
        emb = sim[idx].astype(float)
        t_emb = time.time()

        query_uri = jpeg_data_uri(image, self.s.image_side)
        degraded = False
        try:
            p = np.array(list(self.pool.map(lambda s: self.verifier.p_yes(self.ref_uri(s), query_uri), cands)))
        except Exception as e:  # verifier down or slow: fall back to the embedding ranking
            log.warning("verifier failed, using embedding ranking: %s", e)
            p, degraded = np.zeros(len(cands)), True
        score = self.s.fusion_a * (emb - emb.max()) / self.s.fusion_t + p
        order = np.argsort(-score)
        ranked = [{"slug": cands[i], "name": self.bundle.name(cands[i]), "score": round(float(score[i]), 4),
                   "p_yes": None if degraded else round(float(p[i]), 4), "cosine": round(float(emb[i]), 4)} for i in order]
        t_ver = time.time()

        tiebreak = None
        best = ranked[0]["slug"]
        twins = self.bundle.twins.get(best)
        if twins and self.s.tiebreak and not degraded:
            try:
                tiebreak = self.verifier.tiebreak(query_uri, [best] + twins, self.bundle.card_info)
            except Exception as e:
                log.warning("tie-break failed: %s", e)
            if tiebreak and tiebreak != best:
                pos = next((k for k, c in enumerate(ranked) if c["slug"] == tiebreak), None)
                item = ranked.pop(pos) if pos is not None else {
                    "slug": tiebreak, "name": self.bundle.name(tiebreak), "score": ranked[0]["score"],
                    "p_yes": ranked[0]["p_yes"], "cosine": None}
                ranked = [item] + ranked
                ranked = ranked[: self.s.top_k]

        confidence = ranked[0]["p_yes"]
        return {
            "slug": ranked[0]["slug"],
            "confidence": confidence,
            "low_confidence": degraded or confidence is None or confidence < self.s.low_confidence,
            "margin": round(ranked[0]["score"] - ranked[1]["score"], 4) if len(ranked) > 1 else None,
            "candidates": ranked,
            "tiebreak": tiebreak,
            "degraded": degraded,
            "timings_ms": {"embed": round((t_emb - t0) * 1000), "verify": round((t_ver - t_emb) * 1000),
                           "total": round((time.time() - t0) * 1000)},
        }
