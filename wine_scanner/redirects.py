"""Post-processing of the answer: a kosher card is replaced by its regular (non-kosher) counterpart.

Case organizers confirmed that answering the non-kosher version for a kosher bottle is not counted as an error,
while the reference photos of a kosher card and its regular card are almost the same picture, so the models
often pick the kosher card for a regular bottle. The rule is applied last, after fusion and the twin tie-break.

Only cards that have a regular counterpart in the catalog are listed. "Русское Игристое кошерное брют" has none
(there is no regular "Русское Игристое брют" card), so it is deliberately not redirected.
"""

REDIRECTS = {
    # Русское Игристое кошерное полусладкое -> Русское Игристое полусладкое
    "abrau-dyurso-russkoe-igristoe-koshernoe-polusladkoe-shardone-beloe-12":
        "abrau-dyurso-russkoe-igristoe-polusladkoe-shardone-beloe-12",
    # Victor Dravigny. Кошерное брют -> Абрау-Дюрсо Victor Dravigny брют (same reference photo)
    "abrau-dyurso-victor-dravigny-koshernoe-bryut-shardone-beloe-125":
        "abrau-dyurso-victor-dravigny-bryut",
}


def apply_redirects(ranked, name_of, top_k, redirects=REDIRECTS, known=None):
    """ranked: candidate dicts, best first. Returns (ranked, redirected_from|None).
    The target moves to the front (or is inserted with the source card's score); the source card stays second."""
    if not ranked:
        return ranked, None
    src = ranked[0]["slug"]
    dst = redirects.get(src)
    if not dst or dst == src or (known is not None and dst not in known):
        return ranked, None
    pos = next((k for k, c in enumerate(ranked) if c["slug"] == dst), None)
    if pos is not None:
        item = ranked.pop(pos)
    else:
        item = {"slug": dst, "name": name_of(dst), "score": ranked[0]["score"], "p_yes": ranked[0]["p_yes"], "cosine": None}
    return ([item] + ranked)[:top_k], src
