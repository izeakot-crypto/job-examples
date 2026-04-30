import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    CloseRequest,
    CloseResponse,
    CreateRequest,
    CreateResponse,
    ErrorResponse,
    MessageRequest,
    MessageResponse,
    ResumeRequest,
    ResumeResponse,
)
from app.session import SessionManager

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("lira")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Universal API for connecting AI assistants (OpenAI, Claude, n8n) to Oki-Toki LIRA.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SessionManager()


def _error(status: int, reason: str) -> JSONResponse:
    """Return error in spec format: {"error": {"reason": "..."}}"""
    return JSONResponse(status_code=status, content={"error": {"reason": reason}})


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)
    log.info("%s %s → %s (%dms)", request.method, request.url.path, response.status_code, elapsed)
    return response


# ── Endpoints ─────────────────────────────────────────────


@app.post(
    "/assistant/create",
    response_model=CreateResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create assistant session",
    description="Initialize a new assistant session with a given provider.",
)
async def assistant_create(req: CreateRequest):
    try:
        sid = await manager.create(req)
        log.info("Session created: %s (provider=%s, comp=%d)", sid, req.provider, req.comp_id)
        return CreateResponse(assistant_session_id=sid)
    except ValueError as e:
        log.warning("Create failed (bad request): %s", e)
        return _error(400, str(e))
    except Exception as e:
        log.error("Create failed: %s", e, exc_info=True)
        return _error(500, str(e))


@app.post(
    "/assistant/resume",
    response_model=ResumeResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Resume assistant session",
    description="Resume an existing assistant session by ID.",
)
async def assistant_resume(req: ResumeRequest):
    try:
        sid = await manager.resume(req.comp_id, req.assistant_session_id)
        log.info("Session resumed: %s", sid)
        return ResumeResponse(assistant_session_id=sid)
    except KeyError as e:
        return _error(404, str(e))
    except PermissionError as e:
        return _error(403, str(e))


@app.post(
    "/assistant/message",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Send message to assistant",
    description="Send messages to an active assistant session and get a completion.",
)
async def assistant_message(req: MessageRequest):
    try:
        completion = await manager.message(
            req.comp_id, req.assistant_session_id, req.messages,
        )
        log.info(
            "Message completed: session=%s, tokens_in=%d, tokens_out=%d",
            req.assistant_session_id, completion.tokens_send, completion.tokens_received,
        )
        return MessageResponse(completion=completion)
    except KeyError as e:
        return _error(404, str(e))
    except PermissionError as e:
        return _error(403, str(e))
    except Exception as e:
        log.error("Message failed: session=%s, error=%s", req.assistant_session_id, e, exc_info=True)
        return _error(500, str(e))


@app.post(
    "/assistant/close",
    response_model=CloseResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Close assistant session",
    description="Close an assistant session and clean up provider resources.",
)
async def assistant_close(req: CloseRequest):
    try:
        await manager.close(req.comp_id, req.assistant_session_id)
        log.info("Session closed: %s", req.assistant_session_id)
        return CloseResponse()
    except KeyError as e:
        return _error(404, str(e))
    except PermissionError as e:
        return _error(403, str(e))


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
