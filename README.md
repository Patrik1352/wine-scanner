# wine-scanner — распознавание вина по фото этикетки

 https://disk.yandex.ru/d/LFRjpcVSQnxhOQ вот тут reference_bundle.zip

Сервис принимает фотографию бутылки и возвращает `slug` наиболее подходящей карточки каталога. Каталог содержит 2103 карточки.

Пайплайн состоит из двух этапов:

1. Ансамбль из 3 SigLIP/SigLIP2-энкодеров с LoRA сравнивают фото со всеми эталонами и выбирают top-5.
2. Qwen3.5-4B с LoRA проверяет пары «эталон (таргетное фото) ↔ фото покупателя» и переранжирует кандидатов. Для карточек с одинаковым эталоном дополнительный запрос к базовой Qwen читает текст этикетки.

Если сервис не может найти подходящего кандидата, то явно это показывает.

Подробная схема — в [ARCHITECTURE.md](ARCHITECTURE.md).

## Компоненты

Система запускается двумя процессами:

- **vLLM** — Qwen3.5-4B и verifier LoRA, внутренний порт `8000`;
- **API** — FastAPI, три энкодера и reference bundle, порт `8080`.

Cуммарное потребление VRAM составляет около 28.5 ГБ.

## Структура репозитория

| путь | назначение |
|---|---|
| `wine_scanner/` | FastAPI и recognition pipeline |
| `adapters/embed_v*/` | LoRA трёх энкодеров, хранятся в Git |
| `adapters/verifier/` | LoRA Qwen, хранится через Git LFS |
| `scripts/` | загрузка моделей, запуск процессов, построение индекса |
| `eval/case/` | неизменённый проверочный набор кейсодержателя |
| `artifacts/reference_bundle/` | приватные эталоны и индексы, в Git не хранится |

## Модели и артефакты

Перед запуском необходимы:

1. Подтянуть LoRA-адаптеры:

   ```bash
   git lfs install
   git lfs pull
   test "$(wc -c < adapters/verifier/adapter_model.safetensors)" -gt 100000000
   ```

2. Скачать предобработанный каталог с фотографиями в `artifacts/reference_bundle/`:

   ```text
   manifest.json
   photos/<slug>.*
   index_v1.npz
   index_v2.npz
   index_v3.npz
   catalog.jsonl
   equivalence.json
   twins.json
   card_info.json
   ```

   В данном каталоге помимо фотографий хранятся вектора и прочие технические файлы.

3. Публичные базовые модели из `models.lock.json`. Они скачиваются автоматически при первом запуске без HF-токена. 

Эталонные фотографии являются данными организаторов и не хранятся открыто в репозитории.

## Запуск

Поддерживаются Python 3.10–3.11 и CUDA 12.x. API (бэк) и vLLM устанавливаются в разные окружения:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

python3 -m venv .venv-vllm
.venv-vllm/bin/pip install -r requirements-vllm.txt
```

Опционально можно загрузить все базовые модели заранее:

```bash
HF_HOME=/absolute/path/to/hf-cache \
  .venv/bin/python scripts/download_models.py
```

Запуск:

```bash
cp .env.example .env
set -a; . ./.env; set +a
VLLM_BIN=.venv-vllm/bin/vllm bash scripts/run_vllm.sh
PYTHON=.venv/bin/python bash scripts/run_api.sh
curl -s http://127.0.0.1:8080/health/ready
```

Остановка сервисов:

```bash
bash scripts/stop.sh
```

## API

| метод | путь | назначение |
|---|---|---|
| `GET` | `/health/live` | процесс API работает |
| `GET` | `/health/ready` | модели, reference bundle и vLLM готовы |
| `POST` | `/v1/eval/predict` | top-5 кандидатов; элемент `[0]` является ответом |
| `POST` | `/v1/recognize` | контракт приложения с уверенностью и таймингами |
| `GET` | `/v1/wines/{slug}` | карточка вина |

Пример распознавания:

```bash
curl -s -F "image=@/path/to/wine.jpg" \
  http://127.0.0.1:8080/v1/recognize
```

Поддерживаются JPEG, PNG, WebP, BMP, TIFF и HEIC при наличии `pillow-heif`. Ограничения по умолчанию: 25 МБ и 64 Мп. Если vLLM недоступен, API возвращает результат энкодеров с `degraded: true`.

## Проверка на данных кейсодержателя

Проверочный набор содержит манифест `query_id<TAB>image_path` и отправляет фотографии последовательно, без повторов и параллелизма. Перед запуском дождитесь `200` от `/health/ready`:

```bash
bash eval/run_check.sh \
  --images-dir eval/case/queries \
  --manifest eval/case/queries.tsv
```

Результат сохраняется в `eval/results/predictions_<timestamp>.jsonl`. Обёртка печатает `slug`, задержку каждого запроса, median, p90, max, число пустых ответов и таймаутов. Правильные ответы отсутствуют: точность и итоговый confidence рассчитывает организатор.

Для размеченного собственного набора со структурой `<gold_slug>/<photo>`:

```bash
.venv/bin/python scripts/evaluate.py --data /path/to/photos_by_slug
```

## Качество

Результаты для reference bundle v4 и тестов от 28.09.2026:

| набор | embeddings top-1 | верный в top-5 | итог Qwen |
|---|---:|---:|---:|
| 1327 фото с ответом | 85.5% | 98.2% | 89.1% |
| полевые фото, 672 | 88.4% | — | 93.8% |
| «новые фото 5», 78 | 74.4% | 94.9% | 79.5% |

Оценка учитывает эквивалентные карточки из `equivalence.json`. Строгая точность по slug ниже на 3–5 процентных пунктов.

## Обновление эталонов

Замените или добавьте фото как `artifacts/reference_bundle/photos/<slug>.<ext>`, затем создайте новую версию индекса:

```bash
.venv/bin/python scripts/build_index.py --version v5
```

Пересчитываются только новые или изменённые фото, а также `twins.json` и `manifest.json`.

## Основные настройки

| переменная | значение по умолчанию | назначение |
|---|---|---|
| `WS_BUNDLE_DIR` | `artifacts/reference_bundle` | reference bundle |
| `WS_VLLM_URL` | `http://127.0.0.1:8000` | URL verifier API |
| `WS_DEVICE` | `cuda:0` | GPU энкодеров |
| `WS_TOP_K` | `5` | число проверяемых кандидатов |
| `WS_LOW_CONFIDENCE` | `0.3` | порог `low_confidence` |
| `WS_IMAGE_SIDE` | `1600` | длинная сторона фото для Qwen |
| `WS_WARM_REFS` | `1` | прогрев кэша эталонов |
| `WS_VERIFY_BUNDLE` | `1` | проверка SHA-256 bundle при старте |
| `WS_VERIFIER_TIMEOUT` | `8` | переход в degraded mode, секунды |
| `WS_CORS_ORIGINS` | `*` | разрешённые origins |
| `HF_HOME` | стандартный HF cache | кэш при нативном запуске |

## Ограничения

- Сервис рассчитан только на вина предоставленного каталога.
- Одна бутылка в кадре распознаётся лучше, чем несколько бутылок на полке.
- Похожие вина одной линейки остаются основным источником ошибок.
- GPU-запросы API выполняются последовательно, при параллельной нагрузке задержка растёт.
- Публичный API не имеет встроенной аутентификации.
