# Быстрый старт

## Что нужно для работы

1. **Git** — для клонирования репозитория
2. **Docker** + **Docker Compose** — для запуска сервисов
3. **Python 3.11+** — для локальной разработки и тестов (опционально)

## Клонирование репозитория

```bash
git clone https://bitbucket.org/dintsin010/py-services.git
cd py-services
```

## Настройка окружения

Скопируй шаблон .env и заполни реальными значениями:

```bash
cp .env.example .env
nano .env   # или любой редактор
```

Обязательные переменные:
- `OLLAMA_URL` — URL Ollama/AgentCC API
- `OLLAMA_MODEL` — модель для анализа
- `OLLAMA_API_KEY` — ключ API
- `TC_API_KEY` — API ключ для translation-checker
- `TC_DISCORD_WEBHOOK` — вебхук Discord для алертов

## Запуск

```bash
docker compose up -d --build
```

Это поднимет три контейнера:
- **py-services-gateway** — Nginx Gateway (SSL + роутинг) на портах 80/443
- **py-services-prod** — prod-контейнер (main ветка) с supervisord + внутренний Nginx + Python-сервисы
- **py-services-test** — test-контейнер (staging ветка), идентичный prod

## Проверка

```bash
# PROD health check
curl https://py-services.oki-toki.net/api/translation-checker/health
# Ответ: {"status": "ok", "service": "translation-checker", "environment": "prod"}

# TEST health check
curl https://py-services.oki-toki.net/test/translation-checker/health
# Ответ: {"status": "ok", "service": "translation-checker", "environment": "test"}
```

## URL-схема

| Среда | URL | Swagger | Каталог |
|-------|-----|---------|---------|
| Prod | `/api/<service>/...` | `/api/<service>/docs` | `/docs` |
| Test | `/test/<service>/...` | `/test/<service>/docs` | `/test-docs` |

Gateway автоматически переписывает `/test/` → `/api/` перед передачей в test-контейнер. Код сервисов одинаковый — различие только в маршрутизации.

## Остановка

```bash
docker compose down
```

## Просмотр логов

```bash
# Все контейнеры
docker compose logs -f

# Только prod
docker compose logs -f prod

# Только test
docker compose logs -f test

# Файловые логи
tail -f /var/log/py-services/prod/translation-checker.log
tail -f /var/log/py-services/test/translation-checker.log
```
