# LIRA Voice Assistants API — Implementation Plan

## Architecture

```
FastAPI (HTTP JSON API)
    │
    ├── /assistant/create   → SessionManager.create()
    ├── /assistant/resume   → SessionManager.resume()
    ├── /assistant/message   → SessionManager.message()
    └── /assistant/close     → SessionManager.close()
                │
        ProviderFactory.get(provider_name)
                │
                ├── OpenAIProvider    (Chat Completions + Assistants API)
                ├── N8NProvider       (n8n API — webhook/workflow execution)
                └── ClaudeProvider    (Anthropic Messages API)
```

## File Structure

```
app/
├── main.py                  # FastAPI app, endpoints
├── models.py                # Pydantic models (request/response)
├── session.py               # SessionManager (in-memory, later Supabase)
├── providers/
│   ├── base.py              # BaseProvider (abstract interface)
│   ├── factory.py           # ProviderFactory
│   ├── openai_provider.py   # OpenAI adapter
│   ├── n8n_provider.py      # n8n adapter
│   └── claude_provider.py   # Claude adapter
├── requirements.txt
└── config.py                # Settings (env vars)
```

## Step-by-step Plan

### Step 1: Project skeleton
- Create `app/` directory structure
- `requirements.txt`: fastapi, uvicorn, httpx, openai, anthropic, pydantic
- `config.py`: базові налаштування через env vars

### Step 2: Pydantic models (`models.py`)
Request/Response моделі для всіх 4 методів:

```python
# CREATE
CreateRequest:
    session_id: str          # ID дзвінка з Oki-Toki
    comp_id: int             # ID компанії
    contact_id: int          # ID контакту
    provider: str            # "openai" | "n8n" | "claude"
    config:
        url: str | None
        api_key: str
        model: str | None
        assistant_id: str | None
        system_prompt: str | None
        temperature: float = 0.7
        max_tokens: int = 1000
    parameters: dict = {}    # vendor-specific

CreateResponse:
    assistant_session_id: str
    # OR
    error: { reason: str }

# RESUME
ResumeRequest:
    comp_id: int
    assistant_session_id: str

# MESSAGE
MessageRequest:
    comp_id: int
    assistant_session_id: str
    messages: [{ role: str, content: str }]

MessageResponse:
    completion:
        text: str
        tokens_sent: int
        tokens_received: int
    # OR
    error: { reason: str }

# CLOSE
CloseRequest:
    comp_id: int
    assistant_session_id: str
```

### Step 3: BaseProvider + Factory (`providers/base.py`, `providers/factory.py`)
Abstract interface:
```python
class BaseProvider:
    async def create_session(config, parameters) -> provider_session_data
    async def send_message(provider_session_data, messages) -> completion
    async def close_session(provider_session_data) -> None
```

Factory maps "openai" → OpenAIProvider, etc.

### Step 4: SessionManager (`session.py`)
- In-memory dict: `{assistant_session_id: SessionData}`
- SessionData stores: provider name, config, provider_session_data, message history
- `create()` → generates assistant_session_id (UUID), calls provider.create_session()
- `resume()` → looks up session, returns it
- `message()` → looks up session, calls provider.send_message()
- `close()` → calls provider.close_session(), removes from dict

### Step 5: OpenAI Provider (`providers/openai_provider.py`)
- If `assistant_id` provided → use Assistants API (create thread, add messages, run)
- Else → use Chat Completions API (stateless, send full history)
- Map to unified response format

### Step 6: Claude Provider (`providers/claude_provider.py`)
- Use Anthropic Messages API
- Send system_prompt + message history
- Map to unified response format

### Step 7: N8N Provider (`providers/n8n_provider.py`)
- Call n8n workflow via webhook/API
- Send messages as payload
- Parse response from workflow output

### Step 8: FastAPI Endpoints (`main.py`)
- 4 POST endpoints mapping to SessionManager methods
- Error handling, validation
- CORS middleware (for future UI)

### Step 9: Basic testing
- Manual test з кожним провайдером
- Перевірити create → message → close flow
