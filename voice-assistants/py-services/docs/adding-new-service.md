# Как добавить новый сервис

## Пошаговая инструкция

### 1. Создай директорию сервиса

```bash
mkdir -p services/my-service/tests
```

### 2. Создай файлы

**services/my-service/__init__.py**
```python
# My Service
```

**services/my-service/requirements.txt**
```
fastapi>=0.104.0
uvicorn>=0.24.0
requests>=2.28.0
setproctitle>=1.3.0
```

**services/my-service/server.py**
```python
#!/usr/bin/env python3
import os
from fastapi import Depends
from pydantic import BaseModel
from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger

SERVICE_NAME = "my-service"
PORT = int(os.environ.get("MS_PORT", 8590))
API_KEY = os.environ.get("MS_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("MS_DISCORD_WEBHOOK", "")

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)

app = create_app(
    service_name=SERVICE_NAME,
    title="My Service API",
    description="Описание сервиса",
    version="1.0.0",
)

# --- Pydantic-модели (обязательно для Swagger UI) ---

class DoSomethingRequest(BaseModel):
    text: str

class DoSomethingResponse(BaseModel):
    status: str
    result: str

# --- Эндпоинты ---

@app.post(
    f"/api/{SERVICE_NAME}/do-something",
    response_model=DoSomethingResponse,
    dependencies=[Depends(require_auth(API_KEY))],
)
async def do_something(body: DoSomethingRequest):
    logger.info(f"Получен запрос: {body.text}")
    return DoSomethingResponse(status="ok", result="done")

if __name__ == '__main__':
    run_service(app, port=PORT, service_name=SERVICE_NAME)
```

**services/my-service/tests/__init__.py**
```python
```

**services/my-service/tests/test_api.py**
```python
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MS_API_KEY", "test_key_123")
os.environ.setdefault("MS_PORT", "8590")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")

from services.my_service.server import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test_key_123"}

class TestHealth:
    def test_health_ok(self):
        r = client.get("/api/my-service/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

class TestAuth:
    def test_no_auth_401(self):
        r = client.post("/api/my-service/do-something", json={"text": "test"})
        assert r.status_code in (401, 403)

    def test_valid_auth(self):
        r = client.post("/api/my-service/do-something", json={"text": "test"}, headers=AUTH)
        assert r.status_code == 200
```

### 3. Добавь requirements в Dockerfile

В корневом `Dockerfile` добавь строки COPY и -r:

```dockerfile
COPY services/my-service/requirements.txt /app/requirements/my-service.txt

RUN pip install --no-cache-dir \
    -r /app/requirements/translation-checker.txt \
    -r /app/requirements/tts-google-chirp3.txt \
    -r /app/requirements/my-service.txt        # <-- новый
```

### 4. Добавь в supervisord.conf

```ini
[program:py-services-my-service]
command=python -u -m services.my-service.server
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
```

### 5. Добавь location в nginx/nginx.conf (внутренний Nginx)

```nginx
    # My Service
    location /api/my-service/ {
        proxy_pass http://127.0.0.1:8590;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

Gateway (gateway.conf) менять **НЕ нужно** — он роутит все `/api/*` и `/test/*` целиком.

### 6. Добавь переменные в .env.example

```env
# ============================================
# My Service (MS)
# ============================================
MS_PORT=8590
MS_API_KEY=your_my_service_api_key
MS_DISCORD_WEBHOOK=https://discord.com/api/webhooks/your/webhook
MS_TG_BOT_TOKEN=your_telegram_bot_token
MS_TG_CHAT_ID=your_telegram_chat_id
```

### 7. Добавь тесты в bitbucket-pipelines.yml

В секцию `run-tests` добавь:
```yaml
          # My Service
          - pip install -r services/my-service/requirements.txt
          - export MS_API_KEY=test_key_123
          - export MS_PORT=8590
          - python -m pytest services/my-service/tests/ -v
```

### 8. Добавь карточку в nginx/docs.html

```html
        <div class="service" id="svc-my-service">
            <div class="service-header">
                <span class="service-name">My Service</span>
                <span class="service-status" id="status-my-service">checking...</span>
            </div>
            <p class="service-desc">Описание сервиса</p>
            <div class="links">
                <a href="/api/my-service/docs">Swagger UI</a>
                <a href="/api/my-service/redoc">ReDoc</a>
                <a href="/api/my-service/health">Health</a>
            </div>
        </div>
```

И в `<script>`:
```javascript
        checkHealth('my-service');
```

### 9. Добавь в таблицу портов в CLAUDE.md

```markdown
| my-service | 8590 | MS_ |
```

### 10. Запусти тесты и проверь

```bash
# Локальные тесты
python -m pytest services/my-service/tests/ -v

# Деплой через git flow
git checkout -b feature/add-my-service
git add .
git commit -m "feat: add my-service"
git push origin feature/add-my-service
# merge в staging → тест на /test/my-service/health
# merge в main → прод на /api/my-service/health
```
