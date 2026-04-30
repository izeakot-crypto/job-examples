# py-services — Правила для Claude Code

## Язык общения

Всегда отвечай на русском языке.

## Проект

Два контейнера `py-services-prod` (main) и `py-services-test` (staging) с Python-микросервисами на FastAPI + Nginx Gateway для SSL и маршрутизации:
- `/api/*` → prod-контейнер (main ветка)
- `/test/*` → test-контейнер (staging ветка), Gateway переписывает `/test/` → `/api/`
- Код сервисов одинаковый, роутинг делает Gateway
- Внутри каждого контейнера: supervisord + внутренний Nginx (HTTP) + Python-сервисы

## Архитектура (ТЗ: 13 пунктов)

### 1. Единый репозиторий для всех микросервисов
Монорепо `py-services` на Bitbucket. Каждый сервис в `services/<name>/`.

### 2. Statusline в зависимости от запущенного сервиса
Каждый сервис при старте вызывает `set_statusline(service_name, port, status)` из `shared/statusline.py`. Использует `setproctitle` — виден в `ps ax | grep py-svc` и `htop`.
Формат: `py-svc <имя>|<статус>|port:<порт>|pid:<pid>|uptime:<время>`
В supervisord имена процессов: `py-services-<name>` (полный префикс контейнера).

### 3. REST интерфейс для вызова сервиса
FastAPI. URL формат: `/api/<service-name>/<endpoint>`. Health check: `/api/<service-name>/health` (без авторизации).

### 4. .env конфигурация
Единый `.env` в корне. Все переменные с уникальным префиксом сервиса:
- `TC_` — translation-checker (TC_PORT, TC_API_KEY, TC_DISCORD_WEBHOOK, TC_TG_BOT_TOKEN, TC_TG_CHAT_ID)
- `OC_` — original-checker
- `EM_` — emotion-markup
- `WP_` — wp-translator
- `TGC_` — tts-google-chirp3
- `LA_` — lira-assistants-api
Общие (без префикса): OLLAMA_URL, OLLAMA_MODEL, OLLAMA_API_KEY, LOG_DIR

### 5. Авторизация через API Key + SSL
- API Key через Bearer token в заголовке Authorization
- SSL через Nginx Gateway (сертификаты /etc/ssl/oki-toki.net/)
- Домен: py-services.oki-toki.net
- **Swagger UI авторизация**: все защищённые эндпоинты ОБЯЗАНЫ использовать FastAPI Dependency `require_auth(api_key)` из `shared/auth.py`. Это автоматически добавляет кнопку "Authorize" в Swagger UI с полем для Bearer-токена. НЕ передавать `Request` вручную для авторизации — использовать `Depends(require_auth(api_key))`. API-ключи НИКОГДА не показываются в коде или Swagger — только поле для ввода.

### 6. Логирование в единый файл с маунтом в /var/log
- Все сервисы логируют через `shared/logger.py` → `get_logger(service_name)`
- RotatingFileHandler в `/var/log/py-services/`
- Volume mount: `/var/log/py-services:/var/log/py-services`
- Формат: `timestamp [LEVEL] [service-name] message`
- **Discord-алерты через logger**: `get_logger(service_name, discord_webhook=XX_DISCORD_WEBHOOK)` автоматически добавляет `DiscordHandler`. Уровни WARNING и выше (WARNING, ERROR, CRITICAL) отправляются в Discord. INFO и DEBUG — только в файл и stdout.
- **Rate limit**: не чаще 1 сообщения одного типа в 30 секунд (защита от спама при массовых ошибках)
- **Формат Discord-сообщений**: WARNING — оранжевый, ERROR/CRITICAL — красный. Поля: сервис, сервер, сообщение.
- Если `discord_webhook` не передан или пустой — DiscordHandler не добавляется, логгер работает как раньше (файл + stdout)

### 7. Интеграция с Discord
- Каждый сервис имеет свой Discord webhook (уникальная переменная: TC_DISCORD_WEBHOOK, OC_DISCORD_WEBHOOK и т.д.)
- Общий модуль: `shared/discord.py` → `DiscordNotifier`
- Алерты при проблемах + нотификации при деплое
- **Автоматические алерты**: через `DiscordHandler` в logger — любой `logger.warning()` или `logger.error()` автоматически уходит в Discord (если webhook задан)

### 8. Автогенерация Swagger UI для каждого сервиса
- Каталог всех сервисов: `/docs` (prod) и `/test-docs` (test) — статическая HTML-страница (`nginx/docs.html`)
- Prod Swagger UI: `/api/<service-name>/docs`
- Test Swagger UI: `/test/<service-name>/docs`
- `root_path` из env обеспечивает корректные URL в Swagger для test-контейнера
- При добавлении нового сервиса — добавить карточку в `nginx/docs.html`

### 9. CI/CD на уровне Bitbucket
`bitbucket-pipelines.yml`:
- `feature/*` → только тесты
- `staging` → тесты → деплой TEST-контейнера → health check `/test/.../health` → rollback
- `main` → тесты → деплой PROD-контейнера → health check `/api/.../health` → rollback

### 10. Автоматические тесты при deploy
pytest в пайплайне. Тесты падают → деплой не идёт.

### 11. Автоматический rollback при провале health checks
После деплоя пайплайн дёргает `/health` каждого сервиса. Не отвечает за 5 попыток → `git checkout HEAD~1` → пересборка → Discord алерт.

### 11.1. Discord-нотификации о деплоях
В `bitbucket-pipelines.yml` после деплоя и после rollback отправляется нотификация в Discord через webhook (`DISCORD_DEPLOY_WEBHOOK` — переменная в Bitbucket Pipelines). Сообщения включают: контейнер (PROD/TEST), ветку, коммит, описание коммита (`git log -1 --pretty=%s`), ссылку на Jira-задачу (если ключ `[A-Z]+-[0-9]+` найден в subject коммита). Успешный деплой — NOTICE, rollback — ERROR (красный). Подробнее: `docs/jira-integration.md`.

### 12. Обязательные тесты для каждого сервиса и контейнера
Каждый сервис ОБЯЗАН иметь `tests/test_api.py` с минимум:
- health check тест
- auth тест (401 без ключа)
- базовый функциональный тест
CI не пропустит без тестов.

### 13. Claude Code как штатный coding tool
Этот файл (CLAUDE.md) — единые правила. Влияет на всех, кто работает с Claude Code в этом репозитории.

## Структура

```
py-services/
├── Dockerfile              # Единый — собирает контейнер (prod и test одинаковые)
├── supervisord.conf        # Управление процессами (nginx + все сервисы)
├── docker-compose.yml      # 3 сервиса: gateway, prod, test
├── nginx/
│   ├── gateway.conf        # Nginx Gateway (SSL + роутинг /api/→prod, /test/→test)
│   ├── nginx.conf          # Внутренний Nginx (HTTP, внутри контейнера)
│   └── docs.html           # Каталог API документации
├── services/
│   ├── __init__.py
│   └── <name>/
│       ├── server.py       # FastAPI-приложение (точка входа)
│       ├── requirements.txt
│       ├── tests/test_api.py
│       └── __init__.py
├── shared/                 # Общие модули (НЕ дублировать в сервисах!)
│   ├── logger.py           # get_logger(service_name)
│   ├── auth.py             # require_auth(api_key)
│   ├── discord.py          # DiscordNotifier
│   ├── statusline.py       # set_statusline()
│   └── base_service.py     # create_app(), run_service() — root_path для test
├── conftest.py             # Регистрация сервисов с дефисами для pytest
├── bitbucket-pipelines.yml # CI/CD (staging→test, main→prod)
├── .env.example            # Шаблон переменных окружения
└── docs/                   # Документация
```

## Правила кода

- Python 3.11+, FastAPI
- Конфигурация: только через .env (НЕ config.json)
- Логирование: только через `shared.logger.get_logger(service_name, discord_webhook=...)`. Для Discord-алертов передать webhook — WARNING+ автоматически уйдёт в Discord (rate limit 30с)
- Авторизация: только через `Depends(require_auth(api_key))` из `shared.auth` — это FastAPI Dependency, которая автоматически интегрируется со Swagger UI (кнопка "Authorize"). НЕ передавать Request вручную.
- Statusline: вызывать `set_statusline()` при старте каждого сервиса
- Все переменные с уникальным префиксом сервиса (TC_, OC_, EM_, WP_)
- **Swagger UI**: все эндпоинты ОБЯЗАНЫ использовать Pydantic-модели для request body и response. Это обеспечивает интерактивный Swagger с примерами и возможностью тестирования через "Try it out". НЕ использовать сырой `Request` для получения JSON — использовать типизированные Pydantic-модели.

## Создание нового сервиса

1. Создай директорию `services/<name>/`
2. Создай файлы: `server.py`, `__init__.py`, `requirements.txt`, `tests/test_api.py`
3. В `server.py` используй shared модули (base_service, auth, logger, statusline)
4. Все переменные с префиксом: `XX_PORT`, `XX_API_KEY`, `XX_DISCORD_WEBHOOK`, `XX_TG_BOT_TOKEN`, `XX_TG_CHAT_ID`
5. Добавь requirements в `Dockerfile` (COPY + pip install)
6. Добавь `[program:py-services-<name>]` в `supervisord.conf`
7. Добавь `location` блок в `nginx/nginx.conf` (внутренний Nginx)
8. Добавь переменные в `.env.example`
9. Добавь тесты в `bitbucket-pipelines.yml`
10. Добавь карточку сервиса в `nginx/docs.html`

## Деплой

- Сервер: SSH порт 1300
- Два git-клона на сервере:
  - `/opt/py-services/` — main ветка (prod + docker-compose.yml + gateway)
  - `/opt/py-services-test/` — staging ветка (код для test-контейнера)
- Три контейнера: `py-services-gateway` (nginx:alpine), `py-services-prod`, `py-services-test`
- Деплой staging → обновляет `/opt/py-services-test/`, пересобирает только test-контейнер
- Деплой main → обновляет `/opt/py-services/`, пересобирает только prod-контейнер
- `docker compose up -d --no-deps test/prod` — пересобирать без рестарта gateway
- SSH-ключ для деплоя: base64-закодирован в переменной SSH_KEY_B64
- В pipelines НЕ использовать heredoc (`<< 'EOF'`) — Bitbucket их не поддерживает в `|` блоках

## Запреты

- НЕ создавай config.json — используй .env
- НЕ создавай отдельный Dockerfile для сервиса — один Dockerfile в корне
- НЕ дублируй код из shared/ в сервисах
- НЕ используй print() — только logger
- НЕ хардкодь URL, ключи, порты — всё из переменных окружения
- НЕ коммить .env файл (он в .gitignore)
- НЕ удаляй и не изменяй тесты других сервисов
- НЕ меняй порты без согласования
- НЕ пуш напрямую в main или staging — сначала feature/*, тесты, потом локальный merge в staging
- НЕ используй heredoc в bitbucket-pipelines.yml внутри `|` блоков

## Порты

| Сервис | Порт | Префикс |
|--------|------|---------|
| translation-checker | 8585 | TC_ |
| original-checker | 8586 | OC_ |
| emotion-markup | 8587 | EM_ |
| wp-translator | 8588 | WP_ |
| tts-google-chirp3 | 8589 | TGC_ |
| lira-assistants-api | 8590 | LA_ |

## Git flow

- `feature/*` → только тесты (разработка новых фич)
- `staging` → тесты → деплой TEST-контейнера → health check `/test/.../health`
- `main` → тесты → деплой PROD-контейнера → health check `/api/.../health`
- Порядок: `feature/*` → тесты → merge в `staging` → деплой TEST → проверка → merge в `main` → деплой PROD
- НЕ пуш напрямую в main или staging без feature-ветки
- Домен: https://py-services.oki-toki.net
- Prod URL: `/api/<service>/...`
- Test URL: `/test/<service>/...`
