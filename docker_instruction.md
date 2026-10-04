# Запуск Docker-образов Wine Scanner

Инструкция для переноса и запуска API, фронтенда и vLLM на новом сервере.

## Требования

- Linux `amd64` с NVIDIA GPU.
- Docker Engine, Docker Compose и настроенный NVIDIA Container Toolkit.
- Входящий TCP-порт `3000`, если фронтенд должен быть доступен напрямую из интернета.

## 1. Загрузить образы

Поместите архив `wine-scanner-images.tar.gz` на новый сервер и выполните:

```bash
gunzip -c /root/wine-scanner-images.tar.gz | docker load
```

Убедитесь, что загружены все три образа:

```bash
docker image ls
```

Должны присутствовать `wine-scanner-api:latest`, `wine-scanner-frontend:latest` и `vllm/vllm-openai:v0.19.1`.

## 2. Подготовить Compose-файл и данные

Создайте каталоги проекта и смонтированных данных:

```bash
mkdir -p /root/wine-scanner/docker /root/wine-scanner/adapters /root/wine-scanner/artifacts /root/.cache/huggingface
```

Скопируйте актуальный `docker/docker-compose.yml` из проекта в `/root/wine-scanner/docker/docker-compose.yml`. Например, через рабочую машину:

```bash
scp root@OLD_SERVER:/root/wine-scanner/docker/docker-compose.yml .
scp docker-compose.yml root@NEW_SERVER:/root/wine-scanner/docker/
```

Замените `OLD_SERVER` и `NEW_SERVER` на адреса соответствующих серверов.

На новый сервер также нужно передать смонтируемые данные: каталог адаптера `adapters/verifier`, каталог `artifacts/reference_bundle` и кэш весов `/root/.cache/huggingface`. Например, со старого сервера, если с него доступен SSH на новый:

```bash
rsync -aH /root/wine-scanner/adapters/ root@NEW_SERVER:/root/wine-scanner/adapters/
rsync -aH /root/wine-scanner/artifacts/reference_bundle/ root@NEW_SERVER:/root/wine-scanner/artifacts/reference_bundle/
rsync -aH /root/.cache/huggingface/ root@NEW_SERVER:/root/.cache/huggingface/
```

Замените `NEW_SERVER` на адрес нового сервера. Можно не переносить HF-кэш, если модельные веса будут скачаны на новом сервере отдельно. Образа Docker не содержат эти адаптеры, справочные данные или веса модели.

## 3. Запустить сервисы

На новом сервере выполните:

```bash
cd /root/wine-scanner
HF_CACHE=/root/.cache/huggingface docker compose -f docker/docker-compose.yml up -d --no-build
```

Флаг `--no-build` использует уже загруженные образы и не запускает их сборку.

## 4. Дождаться готовности и проверить

Посмотрите статусы контейнеров и логи vLLM:

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f vllm
```

Первая инициализация vLLM может занять несколько минут. Пока модель загружается, API может отвечать `503`. Готовность API проверяется так:

```bash
curl -i http://127.0.0.1:8080/health/ready
```

Продолжайте, когда ответ станет `200 OK` и в JSON будет `"status":"ready"`.

Фронтенд доступен по адресу `http://NEW_SERVER:3000/`. Если он не открывается снаружи, проверьте firewall и разрешите входящие подключения на TCP-порт `3000`. API опубликован только на localhost сервера (`127.0.0.1:8080`).

У контейнеров настроен перезапуск `unless-stopped`: после перезагрузки сервера Docker восстановит их запуск.
