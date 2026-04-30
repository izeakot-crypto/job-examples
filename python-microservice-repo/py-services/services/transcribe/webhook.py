#!/usr/bin/env python3
"""
Відправка результату транскрипції на callback_url з ретраями та Discord алертом.
"""
import asyncio

import httpx

from shared.logger import get_logger
from shared.discord import DiscordNotifier

logger = get_logger("transcribe")

RETRY_DELAYS = [5, 30, 120]  # секунди між спробами: 3 спроби
WEBHOOK_TIMEOUT = 15


async def send_webhook(
    callback_url: str,
    payload: dict,
    task_id: str,
    discord_notifier: DiscordNotifier | None = None,
) -> bool:
    """Відправляє результат на callback_url з ретраями.

    Якщо всі спроби провалились — відправляє алерт в Discord канал Transcribe_errors.

    Args:
        callback_url: URL для POST запиту з результатом.
        payload: Дані для відправки (JSON).
        task_id: ID задачі (для логів).
        discord_notifier: Discord нотифайєр для алертів.

    Returns:
        True якщо успішно відправлено.
    """
    attempts = len(RETRY_DELAYS) + 1

    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                resp = await client.post(callback_url, json=payload)
                if resp.status_code < 500:
                    logger.info(f"[{task_id}] Webhook відправлено (спроба {attempt}), статус {resp.status_code}")
                    return True
                logger.warning(f"[{task_id}] Webhook повернув {resp.status_code} (спроба {attempt})")
        except Exception as e:
            logger.warning(f"[{task_id}] Webhook помилка (спроба {attempt}): {e}")

        if attempt <= len(RETRY_DELAYS):
            delay = RETRY_DELAYS[attempt - 1]
            logger.info(f"[{task_id}] Наступна спроба через {delay}с")
            await asyncio.sleep(delay)

    # Всі спроби провалились — алерт в Discord
    error_msg = f"Не вдалось відправити webhook після {attempts} спроб.\nTask ID: `{task_id}`\nCallback URL: `{callback_url}`"
    logger.error(f"[{task_id}] {error_msg}")

    if discord_notifier:
        discord_notifier.send_alert(
            title="Transcribe: webhook failed",
            description=error_msg,
            fields=[
                {"name": "Task ID", "value": task_id, "inline": True},
                {"name": "Callback URL", "value": callback_url, "inline": False},
            ],
        )

    return False
