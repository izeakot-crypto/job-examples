#!/usr/bin/env python3
"""
Redis черга + asyncio воркер для обробки задач транскрипції.

Схема:
  POST /add-task → кладе задачу в Redis list "transcribe:queue"
  Worker (asyncio loop) → бере задачу, скачує аудіо, відправляє на Whisper, шле webhook
"""
import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict

import httpx
import redis.asyncio as aioredis

from shared.logger import get_logger
from shared.discord import DiscordNotifier

from .whisper_client import WhisperClient
from .webhook import send_webhook

logger = get_logger("transcribe")

REDIS_URL          = os.environ.get("TR_REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY          = "transcribe:queue"
RESULT_TTL         = 2 * 3600   # 2 години
TASK_TTL           = 24 * 3600  # 1 день
DOWNLOAD_TIMEOUT   = 30
WORKER_CONCURRENCY = int(os.environ.get("TR_WORKER_CONCURRENCY", 3))


@dataclass
class TranscribeTask:
    task_id:      str
    source_url:   str
    locale:       str
    callback_url: str
    created_at:   float


class TranscribeQueue:
    """Redis черга + пул asyncio воркерів."""

    def __init__(self, whisper: WhisperClient, discord_notifier: DiscordNotifier | None = None):
        self.whisper           = whisper
        self.discord_notifier  = discord_notifier
        self._redis: aioredis.Redis | None = None
        self._workers: list[asyncio.Task] = []

    async def start(self):
        self._redis = aioredis.from_url(REDIS_URL, decode_responses=False)
        for i in range(WORKER_CONCURRENCY):
            task = asyncio.create_task(self._worker(i), name=f"transcribe-worker-{i}")
            self._workers.append(task)
        logger.info(f"Transcribe queue запущено, {WORKER_CONCURRENCY} воркерів")

    async def stop(self):
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        if self._redis:
            await self._redis.aclose()
        logger.info("Transcribe queue зупинено")

    def enqueue(self, source_url: str, locale: str, callback_url: str) -> str:
        """Кладе задачу в чергу. Повертає task_id."""
        task_id = hashlib.md5(f"{uuid.uuid4()}_{time.time()}".encode()).hexdigest()
        task = TranscribeTask(
            task_id=task_id,
            source_url=source_url,
            locale=locale,
            callback_url=callback_url,
            created_at=time.time(),
        )
        # asyncio.get_event_loop() deprecated в Python 3.10+ — використовуємо get_running_loop
        loop = asyncio.get_running_loop()
        loop.create_task(self._push(task))
        return task_id

    async def _push(self, task: TranscribeTask):
        data = json.dumps(asdict(task)).encode()
        await self._redis.rpush(QUEUE_KEY, data)
        await self._redis.setex(f"transcribe:task:{task.task_id}", TASK_TTL, b"pending")
        logger.info(f"[{task.task_id}] Задача додана в чергу. URL: {task.source_url}")

    async def _worker(self, worker_id: int):
        """Asyncio воркер — бере задачі з Redis і обробляє."""
        logger.info(f"Worker-{worker_id} запущено")
        while True:
            try:
                raw = await self._redis.blpop(QUEUE_KEY, timeout=5)
                if raw is None:
                    continue

                _, data = raw
                task_data = json.loads(data)
                task = TranscribeTask(**task_data)

                logger.info(f"[Worker-{worker_id}] Взяв задачу {task.task_id}")
                await self._process(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Worker-{worker_id}] Помилка: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process(self, task: TranscribeTask):
        """Основна логіка обробки однієї задачі."""
        try:
            # 1. Скачати аудіо
            logger.info(f"[{task.task_id}] Скачую аудіо: {task.source_url}")
            audio_data, filename = await self._download(task.source_url)

            # 2. Відправити на Whisper
            logger.info(f"[{task.task_id}] Відправляю на Whisper, locale={task.locale or 'auto'}")
            items = await self.whisper.transcribe(audio_data, filename, task.locale)

            # 3. Зберегти результат в Redis
            result = {
                "done":      True,
                "id":        task.task_id,
                "createdAt": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                "items":     items,
            }
            await self._redis.setex(
                f"transcribe:result:{task.task_id}",
                RESULT_TTL,
                json.dumps(result, ensure_ascii=False).encode(),
            )

            # 4. Відправити webhook
            if task.callback_url:
                await send_webhook(
                    callback_url=task.callback_url,
                    payload=result,
                    task_id=task.task_id,
                    discord_notifier=self.discord_notifier,
                )

            logger.info(f"[{task.task_id}] Оброблено успішно, {len(items)} сегментів")

        except Exception as e:
            logger.error(f"[{task.task_id}] Помилка обробки: {e}", exc_info=True)
            await self._redis.delete(f"transcribe:task:{task.task_id}")

            if self.discord_notifier:
                self.discord_notifier.send_alert(
                    title="Transcribe: помилка обробки задачі",
                    description=str(e),
                    fields=[
                        {"name": "Task ID", "value": task.task_id,   "inline": True},
                        {"name": "Locale",  "value": task.locale or "auto", "inline": True},
                        {"name": "URL",     "value": task.source_url, "inline": False},
                    ],
                )

    async def _download(self, url: str) -> tuple[bytes, str]:
        """Скачує аудіофайл по URL, повертає (bytes, filename)."""
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise FileNotFoundError(f"Файл не знайдено: {url}")
            resp.raise_for_status()
            data = resp.content

        filename = url.split("?")[0].split("/")[-1] or "audio.mp3"
        if "." not in filename:
            filename += ".mp3"

        return data, filename
