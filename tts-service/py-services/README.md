# py-services

A Python FastAPI monorepo with prod and test containers behind an Nginx gateway.

## Architecture

```
              Internet
                 |
        [Nginx Gateway :80/:443]
        SSL termination + routing
              /           \
      /api/* -> prod:80   /test/* -> test:80
             |               |
     [py-services-prod]  [py-services-test]
      (main branch)      (staging branch)
```

- **Gateway** - nginx:alpine, SSL termination, routing `/api/` -> prod, `/test/` -> test
- **Prod** - container from the main branch, internal Nginx + supervisord + Python services
- **Test** - container from the staging branch, identical to prod

## Services

| Service | Port | Description | Status |
|--------|------|-------------|--------|
| translation-checker | 8585 | Translation quality checks | Working |
| tts-google-chirp3 | 8589 | TTS via Google Chirp3-HD (6 languages, cache) | Working |
| lira-assistants-api | 8590 | Universal API for AI assistants (OpenAI, Claude, n8n) | Working |
| original-checker | 8586 | Source text validation | Planned |
| emotion-markup | 8587 | Emotional markup | Planned |
| wp-translator | 8588 | WordPress article translation | Planned |

## Quick Start

```bash
git clone https://bitbucket.org/dintsin010/py-services.git
cd py-services
cp .env.example .env
# fill .env with real values
docker compose up -d --build
```

## API

Domain: `https://py-services.oki-toki.net`

| Environment | URL | Branch |
|------------|-----|--------|
| Prod | `/api/<service>/...` | main |
| Test | `/test/<service>/...` | staging |

All endpoints except `health` require the header:

````
Authorization: Bearer <api_key>
````

## Documentation

- [Quick Start](docs/getting-started.md)
- [How to Add a New Service](docs/adding-new-service.md)
- [Deployment](docs/deployment.md)
- [API Reference](docs/api-reference.md)

## Stack

- Python 3.11 + FastAPI
- Docker + Docker Compose (3 containers: gateway, prod, test)
- Nginx Gateway (SSL + routing) + internal Nginx (HTTP)
- Bitbucket Pipelines (CI/CD: staging -> test, main -> prod)
