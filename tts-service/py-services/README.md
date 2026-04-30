# py-services

Монорепо Python-микросервисов на FastAPI с двумя контейнерами (prod + test) и Nginx Gateway.

## Архитектура

```
              Интернет
                 |
        [Nginx Gateway :80/:443]
        SSL termination + routing
              /           \
      /api/* → prod:80   /test/* → test:80
             |               |
     [py-services-prod]  [py-services-test]
      (main branch)      (staging branch)
```

- **Gateway** — nginx:alpine, SSL-терминация, роутинг `/api/` → prod, `/test/` → test
- **Prod** — контейнер из main ветки, внутренний Nginx + supervisord + Python-сервисы
- **Test** — контейнер из staging ветки, идентичный prod

## Сервисы

| Сервис | Порт | Описание | Статус |
|--------|------|----------|--------|
| translation-checker | 8585 | Проверка качества переводов | Работает |
| tts-google-chirp3 | 8589 | TTS через Google Chirp3-HD (6 мов, кеш) | Работает |
| lira-assistants-api | 8590 | Universal API для AI-асистентів (OpenAI, Claude, n8n) | Работает |
| original-checker | 8586 | Проверка оригиналов | Планируется |
| emotion-markup | 8587 | Эмоциональная разметка | Планируется |
| wp-translator | 8588 | Перевод статей WP | Планируется |

## Быстрый старт

```bash
git clone https://bitbucket.org/dintsin010/py-services.git
cd py-services
cp .env.example .env
# заполнить .env реальными значениями
docker compose up -d --build
```

## API

Домен: `https://py-services.oki-toki.net`

| Среда | URL | Ветка |
|-------|-----|-------|
| Prod | `/api/<service>/...` | main |
| Test | `/test/<service>/...` | staging |

Все эндпоинты (кроме health) требуют заголовок:
```
Authorization: Bearer <api_key>
```

## Документация

- [Быстрый старт](docs/getting-started.md)
- [Как добавить новый сервис](docs/adding-new-service.md)
- [Деплой](docs/deployment.md)
- [API Reference](docs/api-reference.md)

## Стек

- Python 3.11 + FastAPI
- Docker + Docker Compose (3 контейнера: gateway, prod, test)
- Nginx Gateway (SSL + роутинг) + внутренний Nginx (HTTP)
- Bitbucket Pipelines (CI/CD: staging → test, main → prod)
