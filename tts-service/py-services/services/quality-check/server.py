#!/usr/bin/env python3
"""
Quality Check — автоматическая проверка качества звонков колл-центра через LLM.

Эндпоинты:
  POST /api/quality-check/run       — добавить план в очередь на проверку
  GET  /api/quality-check/status    — статус поллера / текущей проверки
  GET  /api/quality-check/audit     — аудит-лог оценки звонка
  GET  /api/quality-check/report    — скачать HTML-отчёт по плану
  GET  /api/quality-check/health    — health check (без авторизации)
"""
import os

from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger

from .poller import PlanPoller

SERVICE_NAME = "quality-check"
PORT = int(os.environ.get("QC_PORT", 8591))
API_KEY = os.environ.get("QC_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("QC_DISCORD_WEBHOOK", "")

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)


# --- Pydantic-модели ---

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
    f"/api/{SERVICE_NAME}/report",
    dependencies=[Depends(require_auth(API_KEY))],
)
async def get_report(
    comp_id: int = Query(description="ID компании"),
    plan_id: int = Query(description="ID плана проверки"),
):
    """Скачать последний HTML-отчёт по прогону плана."""
    import glob
    import os

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
