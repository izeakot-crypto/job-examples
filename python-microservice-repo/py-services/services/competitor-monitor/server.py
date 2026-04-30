#!/usr/bin/env python3
"""
Competitor Monitor — FastAPI сервіс з фоновим scheduler.
Запускає моніторинг конкурентів по розкладу (cron), результати пише в Google Sheets.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger
from shared.statusline import set_statusline

SERVICE_NAME = "competitor-monitor"
PORT = int(os.environ.get("CM_PORT", 8592))
API_KEY = os.environ.get("CM_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("CM_DISCORD_WEBHOOK", "")
# Cron: понеділок 12:30 Київ (09:30 UTC)
SCHEDULE_CRON = os.environ.get("CM_SCHEDULE_CRON", "30 9 * * 1")

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)

# --- Scheduler ---
scheduler = BackgroundScheduler()
_last_run_status: dict = {"status": "never_run"}


def _run_monitoring():
    """Запускає повний цикл моніторингу (викликається scheduler-ом)."""
    global _last_run_status
    from services.competitor_monitor.monitor import run_full_monitoring
    try:
        logger.info("Scheduler: запуск моніторингу конкурентів")
        result = run_full_monitoring()
        _last_run_status = {
            "status": "ok",
            "companies_processed": result.get("processed", 0),
            "last_run": result.get("timestamp", ""),
        }
        logger.info(
            "Scheduler: моніторинг завершено, оброблено %d компаній",
            result.get("processed", 0),
        )
    except Exception as e:
        _last_run_status = {"status": "error", "error": str(e)}
        logger.error("Scheduler: помилка моніторингу: %s", e)


# --- FastAPI app ---
app = create_app(
    service_name=SERVICE_NAME,
    title="Competitor Monitor API",
    description="Автоматичний моніторинг конкурентів по розкладу. Health check + scheduler status.",
    version="1.0.0",
    include_health=False,
)


class SchedulerStatus(BaseModel):
    running: bool
    next_run: str
    cron: str
    last_run: dict

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    scheduler: SchedulerStatus


@app.get(f"/api/{SERVICE_NAME}/health", response_model=HealthResponse)
async def health():
    """Health check з інформацією про scheduler."""
    container_role = os.environ.get("CONTAINER_ROLE", "prod")
    jobs = scheduler.get_jobs()
    next_run = str(jobs[0].next_run_time) if jobs else "no jobs"
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version="1.0.0",
        environment=container_role,
        scheduler=SchedulerStatus(
            running=scheduler.running,
            next_run=next_run,
            cron=SCHEDULE_CRON,
            last_run=_last_run_status,
        ),
    )


class RunResponse(BaseModel):
    status: str
    message: str


@app.post(
    f"/api/{SERVICE_NAME}/run",
    response_model=RunResponse,
    dependencies=[Depends(require_auth(API_KEY))],
)
async def manual_run():
    """Ручний запуск моніторингу (поза розкладом)."""
    import threading
    thread = threading.Thread(target=_run_monitoring, daemon=True)
    thread.start()
    return RunResponse(status="ok", message="Моніторинг запущено у фоні")


@app.on_event("startup")
async def start_scheduler():
    """Запуск scheduler при старті сервісу."""
    parts = SCHEDULE_CRON.split()
    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )
    scheduler.add_job(_run_monitoring, trigger, id="competitor_monitor_cron")
    scheduler.start()
    set_statusline(SERVICE_NAME, port=PORT, status="Running")
    jobs = scheduler.get_jobs()
    next_run = jobs[0].next_run_time if jobs else "?"
    logger.info("Scheduler запущено. Cron: %s. Наступний запуск: %s", SCHEDULE_CRON, next_run)


@app.on_event("shutdown")
async def stop_scheduler():
    """Зупинка scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler зупинено")


if __name__ == "__main__":
    run_service(app, port=PORT, service_name=SERVICE_NAME)
