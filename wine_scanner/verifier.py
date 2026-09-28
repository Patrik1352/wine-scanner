"""Client of the vLLM server that hosts the verifier (Qwen3.5-4B + LoRA, served as `sft`)
and the same base model without the adapter (served as `base`) for the label-text tie-break."""
import math
import re

import requests
from requests.adapters import HTTPAdapter

# Exactly the prompt the verifier LoRA was trained on -- do not edit without retraining.
SYS = "Ты эксперт по винам. Сравниваешь эталонную фотографию вина из каталога и фотографию покупателя."
QUESTION = ("На IMAGE_2 то же самое вино (тот же товар), что и на IMAGE_1? "
            "Учитывай название, производителя, линейку и слово сладости/типа на этикетке "
            "(брют, сухое, полусладкое и т.д.); год урожая и объём не важны. Ответь YES или NO.")

TIEBREAK_PROMPT = (
    "На фото — бутылка вина. Карточки каталога ниже имеют ОДИНАКОВОЕ эталонное фото, отличаются названием, "
    "сладостью, сортом. Прочитай этикетку центральной бутылки и выбери подходящую карточку. Год и объём не важны.\n\n"
    "Карточки:\n{cards}\n\nОтветь ТОЛЬКО JSON: {{\"label_text\": \"текст этикетки\", \"choice\": номер}}")


class Verifier:
    def __init__(self, url, verifier_model="sft", base_model="base", timeout=8.0):
        self.url = url.rstrip("/")
        self.verifier_model, self.base_model, self.timeout = verifier_model, base_model, timeout
        self.http = requests.Session()
        self.http.mount("http://", HTTPAdapter(pool_connections=4, pool_maxsize=64))

    def ready(self) -> bool:
        try:
            r = self.http.get(f"{self.url}/v1/models", timeout=3)
            ids = {m["id"] for m in r.json().get("data", [])}
            return r.ok and self.verifier_model in ids
        except (requests.RequestException, ValueError):
            return False

    def _chat(self, model, messages, **kw):
        r = self.http.post(f"{self.url}/v1/chat/completions", timeout=self.timeout, json={
            "model": model, "messages": messages, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}, **kw})
        r.raise_for_status()
        return r.json()["choices"][0]

    def p_yes(self, ref_uri: str, query_uri: str) -> float:
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": [
            {"type": "text", "text": "IMAGE_1 — эталон из каталога:"}, {"type": "image_url", "image_url": {"url": ref_uri}},
            {"type": "text", "text": "IMAGE_2 — фото покупателя:"}, {"type": "image_url", "image_url": {"url": query_uri}},
            {"type": "text", "text": QUESTION}]}]
        ch = self._chat(self.verifier_model, msgs, max_tokens=1, logprobs=True, top_logprobs=20)
        py = pn = 0.0
        for t in ch["logprobs"]["content"][0]["top_logprobs"]:
            tok = t["token"].strip().upper()
            if tok.startswith("YES"):
                py += math.exp(t["logprob"])
            elif tok.startswith("NO"):
                pn += math.exp(t["logprob"])
        return py / (py + pn) if py + pn else 0.0

    def tiebreak(self, query_uri: str, cands, card_info):
        """Choose among cards that share an identical reference photo by reading the label. None if unsure."""
        cards = "\n".join(f"{i + 1}. {card_info.get(s, s)}" for i, s in enumerate(cands))
        msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": query_uri}},
                                             {"type": "text", "text": TIEBREAK_PROMPT.format(cards=cards)}]}]
        text = self._chat(self.base_model, msgs, max_tokens=200)["message"]["content"]
        m = re.search(r'"choice"\s*:\s*(\d+)', text)
        k = int(m.group(1)) - 1 if m else -1
        return cands[k] if 0 <= k < len(cands) else None
