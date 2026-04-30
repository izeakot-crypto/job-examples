# Деплой

## Архитектура на сервере

```
/opt/py-services/           # main ветка (prod + docker-compose.yml + gateway)
/opt/py-services-test/      # staging ветка (код для test-контейнера)
/var/log/py-services/prod/  # Логи prod-контейнера
/var/log/py-services/test/  # Логи test-контейнера
/etc/ssl/oki-toki.net/      # SSL-сертификаты
```

Три контейнера:
- `py-services-gateway` — nginx:alpine, SSL + роутинг
- `py-services-prod` — main ветка → `/api/*`
- `py-services-test` — staging ветка → `/test/*`

## Автоматический деплой (Bitbucket Pipelines)

### Git flow

```
feature/my-feature  →  staging  →  main
      |                    |           |
   тесты              тесты +     тесты +
                      деплой      деплой PROD +
                      TEST +      Discord +
                      Discord     Jira-комментарий
```

1. Создай ветку `feature/my-feature` от `staging`
2. Работай, коммить, пуши — при каждом пуше запускаются тесты
3. Merge в `staging` → тесты + деплой TEST + health check + Discord-нотификация
4. Merge в `main` → тесты + деплой PROD + health check + Discord-нотификация + Jira-комментарий

### Что делает пайплайн

**staging → TEST:**
1. Тесты (pytest)
2. SSH → обновляет `/opt/py-services-test/` (git pull staging)
3. `docker compose build --no-cache test && docker compose up -d --no-deps test`
4. Health check `/test/translation-checker/health` (5 попыток)
5. При провале — rollback + Discord алерт (ERROR, красный)
6. При успехе — Discord-нотификация (NOTICE) с описанием коммита и ссылкой на Jira

**main → PROD:**
1. Тесты (pytest)
2. SSH → обновляет `/opt/py-services/` (git pull main)
3. `docker compose build --no-cache prod && docker compose up -d --no-deps prod`
4. Health check `/api/translation-checker/health` (5 попыток)
5. При провале — rollback + Discord алерт (ERROR, красный)
6. При успехе — Discord-нотификация (NOTICE) с описанием коммита и ссылкой на Jira
7. Jira — комментарий к задаче (если ключ найден в коммите)

Gateway **не перезапускается** при деплое — `--no-deps` пересобирает только нужный контейнер.

### Discord-нотификации при деплое

При каждом деплое (staging и main) в Discord приходит embed-сообщение:

**Успешный деплой (NOTICE):**
- Sender script name: `bitbucket pipeline`
- Server: `py-services.oki-toki.net`
- Container: `TEST` или `PROD`
- Branch: название ветки
- Commit: хеш коммита (7 символов)
- Описание: subject коммита (первая строка `git log`)
- Задача: ссылка на Jira-задачу (если ключ `PROG-123` найден в subject)

**Rollback (ERROR, красный):**
Те же поля, но title = `ERROR` и описание = `health check failed — rollback executed`.

Переменная `DISCORD_DEPLOY_WEBHOOK` настраивается в Bitbucket → Repository Settings → Repository variables.

### Jira-комментарий при деплое в PROD

Подробнее: [jira-integration.md](jira-integration.md)

## Ручной деплой

### Деплой TEST-контейнера

```bash
ssh -p 1300 root@65.109.131.32

# Обновить код staging
cd /opt/py-services-test
git pull origin staging

# Пересобрать только test
cd /opt/py-services
docker compose build --no-cache test
docker compose up -d --no-deps test

# Проверить
curl https://py-services.oki-toki.net/test/translation-checker/health
```

### Деплой PROD-контейнера

```bash
ssh -p 1300 root@65.109.131.32

# Обновить код main
cd /opt/py-services
git pull origin main

# Пересобрать только prod
docker compose build --no-cache prod
docker compose up -d --no-deps prod

# Проверить
curl https://py-services.oki-toki.net/api/translation-checker/health
```

## Откат (rollback)

```bash
# TEST
cd /opt/py-services-test && git checkout HEAD~1
cd /opt/py-services && docker compose build --no-cache test && docker compose up -d --no-deps test

# PROD
cd /opt/py-services && git checkout HEAD~1
docker compose build --no-cache prod && docker compose up -d --no-deps prod
```

## Просмотр логов

```bash
# Docker логи всех контейнеров
docker compose logs -f

# Только prod
docker compose logs -f prod

# Только test
docker compose logs -f test

# Gateway
docker compose logs -f gateway

# Файловые логи
tail -f /var/log/py-services/prod/translation-checker.log
tail -f /var/log/py-services/test/translation-checker.log
```

## Полная пересборка (все контейнеры)

```bash
cd /opt/py-services
docker compose down
docker compose build --no-cache
docker compose up -d
```
