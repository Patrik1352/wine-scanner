"""python tests/test_redirects.py  (no models needed)"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from wine_scanner.redirects import REDIRECTS, apply_redirects

K = "abrau-dyurso-russkoe-igristoe-koshernoe-polusladkoe-shardone-beloe-12"
R = REDIRECTS[K]
mk = lambda *s: [{"slug": x, "name": x, "score": 1.0 - i / 10, "p_yes": 0.9 - i / 10, "cosine": 0.9} for i, x in enumerate(s)]
name = lambda s: s

# regular card already among candidates -> moves to the front, kosher stays second
r, src = apply_redirects(mk(K, "x", R), name, 5)
assert [c["slug"] for c in r] == [R, K, "x"] and src == K, r
# regular card not among candidates -> inserted with the kosher card's score
r, src = apply_redirects(mk(K, "x"), name, 5)
assert r[0]["slug"] == R and r[0]["score"] == 1.0 and r[1]["slug"] == K and src == K
# list is trimmed to top_k
r, _ = apply_redirects(mk(K, "a", "b", "c", "d"), name, 5)
assert len(r) == 5 and r[0]["slug"] == R
# a non-kosher winner and the kosher брют (no counterpart) are left alone
for s in ("x", "abrau-dyurso-russkoe-igristoe-koshernoe-bryut-shardone-beloe-13"):
    r, src = apply_redirects(mk(s, "y"), name, 5)
    assert r[0]["slug"] == s and src is None
# a target missing from the catalog is ignored
r, src = apply_redirects(mk(K, "y"), name, 5, known={"y"})
assert r[0]["slug"] == K and src is None
# a kosher card that is not the winner is not touched
r, src = apply_redirects(mk("x", K), name, 5)
assert r[0]["slug"] == "x" and src is None
print("ok")
