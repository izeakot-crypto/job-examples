#!/usr/bin/env python3
"""
Quality Check — автоматическая проверка качества звонков колл-центра через LLM.

Эндпоинты:
  POST /api/quality-check/process-call — webhook от Вадима (comp_id, session_id)
  POST /api/quality-check/run          — ручной запуск плана (comp_id, plan_id)
  GET  /api/quality-check/status       — статус поллера / текущей проверки
  GET  /api/quality-check/audit        — аудит-лог оценки звонка
  GET  /api/quality-check/report/{comp_id}/{plan_id} — HTML-отчёт (без авторизации)
  GET  /api/quality-check/health       — health check (без авторизации)
"""
from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger

from .config import settings
from .poller import PlanPoller

SERVICE_NAME = "quality-check"
PORT = settings.qc_port
API_KEY = settings.qc_api_key
DISCORD_WEBHOOK = settings.qc_discord_webhook

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)


# --- Pydantic-модели ---

class ProcessCallRequest(BaseModel):
    """Webhook от Вадима — транскрибация завершена."""
    comp_id: int = Field(description="ID компании")
    session_id: int = Field(description="ID сессии звонка")


class ProcessCallResponse(BaseModel):
    """Ответ на webhook."""
    status: str = Field(description="accepted / ignored / error")
    message: str = Field(description="Описание")
    plans_found: int = Field(default=0, description="Кол-во планов, в которых найден звонок")


class RunRequest(BaseModel):
    """Запрос на запуск проверки."""
    comp_id: int = Field(description="ID компании в Оки-Токи")
    plan_id: int = Field(description="ID плана проверки в Оки-Токи")


class RunResponse(BaseModel):
    """Ответ после запуска проверки."""
    status: str = Field(description="accepted / already_in_queue")
    message: str = Field(description="Описание")
    plan_id: int = Field(description="ID плана")
    queue_size: int = Field(description="Текущий размер очереди")


# --- Поллер ---

poller = PlanPoller()


# --- FastAPI app ---

app = create_app(
    service_name=SERVICE_NAME,
    title="Quality Check API",
    description="Автоматическая проверка качества звонков колл-центра через LLM",
    version="1.1.0",
)


@app.on_event("startup")
async def startup_poller():
    await poller.start()


@app.on_event("shutdown")
async def shutdown_poller():
    await poller.stop()


@app.post(
    f"/api/{SERVICE_NAME}/process-call",
    response_model=ProcessCallResponse,
    dependencies=[Depends(require_auth(API_KEY))],
    status_code=202,
)
async def process_call(body: ProcessCallRequest):
    """Webhook от Вадима: транскрибация завершена.

    Бот проверяет у Саши, есть ли звонок в плане с ботом.
    Если да — добавляет в очередь на обработку.
    """
    from .oki_toki import OkiTokiClient

    try:
        async with OkiTokiClient(comp_id=body.comp_id) as client:
            plans = await client.get_plans_by_session(body.comp_id, body.session_id)
    except Exception as exc:
        logger.error("Ошибка при проверке plans-by-session: %s", exc)
        return ProcessCallResponse(
            status="error",
            message=f"Не удалось проверить планы: {exc}",
        )

    if not plans:
        return ProcessCallResponse(
            status="ignored",
            message=f"session_id={body.session_id} не найден в планах с ботом",
        )

    for plan_id in plans:
        poller.enqueue(body.comp_id, plan_id, body.session_id)

    logger.info(
        "Webhook: session_id=%d (comp_id=%d) -> %d планов: %s",
        body.session_id, body.comp_id, len(plans), plans,
    )

    return ProcessCallResponse(
        status="accepted",
        message=f"Добавлено в очередь для {len(plans)} планов",
        plans_found=len(plans),
    )


@app.post(
    f"/api/{SERVICE_NAME}/run",
    response_model=RunResponse,
    dependencies=[Depends(require_auth(API_KEY))],
)
async def run_check(body: RunRequest):
    """Добавляет план в очередь на проверку.

    Если план уже в очереди или обрабатывается — вернёт already_in_queue.
    """
    added = poller.enqueue(body.comp_id, body.plan_id)

    if not added:
        return RunResponse(
            status="already_in_queue",
            message=f"План {body.plan_id} уже в очереди или обрабатывается",
            plan_id=body.plan_id,
            queue_size=poller.queue_size,
        )

    return RunResponse(
        status="accepted",
        message=f"План {body.plan_id} (comp_id={body.comp_id}) добавлен в очередь",
        plan_id=body.plan_id,
        queue_size=poller.queue_size,
    )


@app.get(
    f"/api/{SERVICE_NAME}/status",
    dependencies=[Depends(require_auth(API_KEY))],
)
async def get_status():
    """Возвращает полный статус поллера: очередь, текущий план, последний результат."""
    return JSONResponse(content=poller.status())


@app.get(
    f"/api/{SERVICE_NAME}/audit",
    dependencies=[Depends(require_auth(API_KEY))],
)
async def get_audit_log(
    comp_id: int = Query(description="ID компании"),
    plan_id: int = Query(description="ID плана проверки"),
    session_id: int = Query(description="ID сессии звонка"),
):
    """Возвращает аудит-лог оценки звонка."""
    from .audit import get_audit

    data = get_audit(comp_id, plan_id, session_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Аудит не найден: comp_id={comp_id}, plan_id={plan_id}, session_id={session_id}",
        )
    return JSONResponse(content=data)


@app.get(
    f"/api/{SERVICE_NAME}/report/{{comp_id}}/{{plan_id}}",
)
async def get_report(comp_id: int, plan_id: int, sig: str = Query(default="", description="HMAC-подпись")):
    """HTML-отчёт по плану проверки. Защищён HMAC-подписью."""
    import glob
    import hashlib
    import hmac
    import os

    from .config import settings

    # Проверяем HMAC-подпись
    if settings.qc_report_secret:
        expected = hmac.new(
            settings.qc_report_secret.encode(),
            f"{comp_id}:{plan_id}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        if sig != expected:
            raise HTTPException(status_code=403, detail="Invalid signature")

    report_dir = os.path.join("audit", str(comp_id), str(plan_id))
    pattern = os.path.join(report_dir, "report_*.html")
    reports = sorted(glob.glob(pattern))

    if not reports:
        raise HTTPException(
            status_code=404,
            detail=f"Отчёт не найден: comp_id={comp_id}, plan_id={plan_id}",
        )

    from fastapi.responses import FileResponse
    return FileResponse(
        reports[-1],
        media_type="text/html",
        filename=os.path.basename(reports[-1]),
    )


if __name__ == "__main__":
    run_service(app, port=PORT, service_name=SERVICE_NAME)
