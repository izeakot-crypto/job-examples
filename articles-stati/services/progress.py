import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def notify_progress(article_id: str, stage: str, percent: int, message: str):
    url = f"{settings.frontend_base_url}/webhook/update-progress"
    payload = {
        "article_id": article_id,
        "progress_stage": stage,
        "progress_percent": percent,
        "progress_message": message,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.warning(f"Progress notification failed: {e}")


async def notify_frontend_save(data: dict):
    url = f"{settings.frontend_base_url}/api/articles/save-for-review"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(url, json=data)
    except Exception as e:
        logger.warning(f"Frontend save notification failed: {e}")
