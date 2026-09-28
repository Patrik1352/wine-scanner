# wine-scanner — распознавание вина по фото этикетки

Фото бутылки → `slug` карточки каталога кейса (2103 вина, `strapi_output0709.csv`).

```
фото ─► 3 энкодера SigLIP/SigLIP2-so400m + LoRA ─► косинус к 2102 эталонам ─► top-5
     ─► верификатор Qwen3.5-4B + LoRA (vLLM): P(YES) «это то же вино?» для каждого из 5
     ─► итог = 0.25·(cos − cos_max)/0.05 + P(YES), кандидаты сортируются по нему
     ─► если у победителя есть «двойники» с побайтно одинаковым эталоном — Qwen3.5-4B (без LoRA)
        читает этикетку и выбирает среди них
```
Ответ — всегда лучший кандидат (по условию кейса все вина из каталога); неуверенность видна по
`confidence` (P(YES) выбранного) и `low_confidence` (< 0.3).

Два процесса, помещаются на одну GPU (~28.5 ГБ на A100-80):
- **vLLM** — верификатор, OpenAI-совместимый API на `127.0.0.1:8000`;
- **API** — FastAPI + энкодеры + индекс, порт `8080`.

## Качество (эталоны v4, test_dataset 28.09.2026, прод-правило выбора)

| набор | эмбеддинги top-1 | верный в top-5 | итог (Qwen) |
|---|---:|---:|---:|
| все 1327 фото с ответом | 85.5% | 98.2% | 89.1% |
| полевые (672, без интернет-фото) | 88.4% | — | 93.8% |
| «новые фото 5» (78), через этот репозиторий | 74.4% | 94.9% | 79.5% |

Точность «с учётом эквивалентных карточек» (`equivalence.json`); строгая по slug ниже на 3–5 п.п.
Задержка на A100 при последовательных запросах: ~0.7 с конвейер, ~1.0 с с приёмом фото 1.2 МБ.

## Что где лежит

| что | в git? | где взять |
|---|---|---|
| код (`wine_scanner/`, `scripts/`) | да | — |
| LoRA энкодеров (`adapters/embed_v{1,2,3}`, по 4 МБ) | да | — |
| версии базовых моделей (`models.lock.json`) | да | модели качаются с HF по закреплённой ревизии |
| LoRA верификатора (`artifacts/verifier_lora`, 117 МБ) | **нет** | приватный HF-репозиторий (см. ниже) |
| набор эталонов (`artifacts/reference_bundle`, 200 МБ) | **нет** | приватный HF dataset-репозиторий |

Эталонные фото — данные организаторов (+12 фото бутылок с сайта vino-svoe.ru) — **не публиковать**.

### Набор эталонов (`artifacts/reference_bundle`)
```
manifest.json      версия, ревизии энкодеров, sha256 каждого файла (проверяется при старте)
photos/<slug>.*    по одному эталону на вино (2102)
index_v{1,2,3}.npz векторы эталонов для каждого энкодера
catalog.jsonl      карточки для GET /v1/wines/{slug}
equivalence.json   slug → группа (одно вино под разными карточками)
twins.json         slug → карточки с побайтно одинаковым эталоном (85 групп)
card_info.json     короткие описания карточек для тай-брейка
```
Текущая версия — **v4** (эталоны `reference_export_v4`, ручная проверка 28.09). Нет эталона только у
`rozovoe-polusladkoe-2` (в каталоге нет фото). У `roze-2` в v4 отсутствовал файл — оставлен прежний эталон.

## Установка

Нужны Python 3.10–3.11, NVIDIA GPU с CUDA 12.x, ~20 ГБ под базовые модели.
vLLM ставится в **отдельное** окружение — у него свои версии torch/CUDA.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt           # API
python3 -m venv .venv-vllm && .venv-vllm/bin/pip install -r requirements-vllm.txt  # верификатор

# артефакты (после того как они выложены на HF; <org> — ваша организация/аккаунт)
huggingface-cli download <org>/wine-scanner-verifier-lora --local-dir artifacts/verifier_lora
huggingface-cli download <org>/wine-scanner-references --repo-type dataset --local-dir artifacts/reference_bundle

.venv/bin/python scripts/download_models.py   # базовые модели в HF-кэш; дальше можно HF_HUB_OFFLINE=1
```

Выложить артефакты (один раз, из этого сервера):
```bash
huggingface-cli upload <org>/wine-scanner-verifier-lora artifacts/verifier_lora . --private
huggingface-cli upload <org>/wine-scanner-references artifacts/reference_bundle . --repo-type dataset --private
```

## Запуск

```bash
cp .env.example .env   # поправить при необходимости
set -a; . ./.env; set +a
VLLM_BIN=.venv-vllm/bin/vllm bash scripts/run_vllm.sh      # ждёт готовности (~1-2 мин)
PYTHON=.venv/bin/python bash scripts/run_api.sh            # ждёт готовности (модели + прогрев эталонов ~1 мин)
curl -s localhost:8080/health/ready
bash scripts/stop.sh                                      # остановить оба (по PID-файлам в logs/)
```
Если базовая модель верификатора лежит не в HF-кэше, а в папке: `VERIFIER_BASE=/path/to/Qwen3.5-4B`.
Если порт 8000 занят: `VLLM_PORT=8010` и `WS_VLLM_URL=http://127.0.0.1:8010`.
По умолчанию оба сервиса слушают только `127.0.0.1`; наружу — `WS_HOST=0.0.0.0` или reverse proxy.

## API

| метод | путь | ответ |
|---|---|---|
| GET | `/health/ready` | 200 — модели загружены, эталоны прогреты, vLLM отвечает; иначе 503 |
| GET | `/health/live` | 200, процесс жив |
| POST | `/v1/eval/predict` | multipart `image` → `[{"slug","score","p_yes","cosine"}, …]` — top-5, **`[0]` — ответ** |
| POST | `/v1/recognize` | multipart `image` → контракт фронтенда: `status:"matched"`, `slug`, `confidence`, `low_confidence`, `alternatives`, `top_k`, `timings_ms` |
| GET | `/v1/wines/{slug}` | карточка вина (404, если нет) |

Ошибки фото: 400 пустое, 413 больше 25 МБ / 64 Мп, 415 неподдерживаемый формат, 422 не читается.
Форматы: JPEG, PNG, WebP, BMP, TIFF; HEIC — если установлен `pillow-heif`.
Если vLLM недоступен, ответ всё равно возвращается по эмбеддингам (`degraded: true`).

`/v1/eval/predict` совместим со скриптом организаторов `participant_test.sh`: он берёт `.[0].slug`,
шлёт запросы по одному с таймаутом 10 с — перед прогоном дождитесь `/health/ready`.

## Проверка качества

```bash
.venv/bin/python scripts/evaluate.py --data /path/<gold_slug>/<photo>   # последовательно, как у организаторов
```

## Обновление эталонов

Заменить/добавить файлы в `artifacts/reference_bundle/photos/<slug>.<ext>`, затем
```bash
.venv/bin/python scripts/build_index.py --version v5
```
Пересчитываются векторы только изменившихся фото, «двойники» и манифест. Код и образ пересобирать не нужно.
`scripts/build_bundle.py` — разовый экспорт набора из исследовательского репозитория (пути по умолчанию —
сервер разработки).

## Настройки (`WS_*`, см. `wine_scanner/config.py`)

`WS_BUNDLE_DIR`, `WS_VLLM_URL`, `WS_DEVICE`, `WS_TOP_K` (5), `WS_FUSION_A` (0.25), `WS_FUSION_T` (0.05),
`WS_LOW_CONFIDENCE` (0.3), `WS_IMAGE_SIDE` (1600 — сторона фото для верификатора), `WS_TIEBREAK` (1),
`WS_WARM_REFS` (1), `WS_VERIFY_BUNDLE` (1), `WS_MAX_BYTES`, `WS_MAX_PIXELS`, `WS_VERIFIER_TIMEOUT` (8 с),
`WS_CORS_ORIGINS` (`*`).

## Docker

`docker/` — запасной вариант (vLLM из официального образа + образ API). **Не проверялся**: на сервере
разработки Docker нет. Основной способ запуска — скрипты выше.
