"""Поллер планов Оки-Токи — опрашивает API и ставит планы в очередь."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from .config import settings
from .oki_toki import OkiTokiClient
from .runner import run_plan, process_single_call, RunProgress

logger = logging.getLogger(__name__)


@dataclass
class PlanTask:
    """Задача на проверку плана или одного звонка."""
    comp_id: int
    plan_id: int
    session_id: int | None = None  # None = весь план, int = один звонок
    queued_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class PlanPoller:
    """Опрашивает Оки-Токи на готовые планы и обрабатывает их по очереди.

    - Поллер: каждые N секунд запрашивает список готовых планов
    - Очередь: планы добавляются в asyncio.Queue (дедупликация по plan_id)
    - Воркер: берёт из очереди по одному и запускает run_plan()
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[PlanTask] = asyncio.Queue()
        self._active_plan_ids: set[int] = set()  # дедупликация планов
        self._active_calls: set[tuple[int, int, int]] = set()  # дедупликация (comp_id, plan_id, session_id)
        self._current_task: PlanTask | None = None
        self._progress: RunProgress | None = None
        self._last_result: dict | None = None
        self._poller_task: asyncio.Task | None = None
        self._worker_task: asyncio.Task | None = None

    @property
    def is_processing(self) -> bool:
        return self._current_task is not None

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def status(self) -> dict:
        """Текущий статус поллера для API."""
        return {
            "polling_enabled": settings.qc_poll_enabled,
            "poll_interval_sec": settings.qc_poll_interval_sec,
            "queue_size": self.queue_size,
            "processing": self.is_processing,
            "current_plan": {
                "comp_id": self._current_task.comp_id,
                "plan_id": self._current_task.plan_id,
                "queued_at": self._current_task.queued_at,
                "progress": self._progress.to_dict() if self._progress else None,
            } if self._current_task else None,
            "last_result": self._last_result,
        }

    def enqueue(self, comp_id: int, plan_id: int, session_id: int | None = None) -> bool:
        """Добавляет план или звонок в очередь. Возвращает False если уже в очереди."""
        if session_id is not None:
            key = (comp_id, plan_id, session_id)
            if key in self._active_calls:
                logger.debug("Звонок %d (plan=%d) уже в очереди", session_id, plan_id)
                return False
            self._active_calls.add(key)
        else:
            if plan_id in self._active_plan_ids:
                logger.debug("План %d уже в очереди", plan_id)
                return False
            self._active_plan_ids.add(plan_id)

        task = PlanTask(comp_id=comp_id, plan_id=plan_id, session_id=session_id)
        self._queue.put_nowait(task)
        label = f"session_id={session_id}" if session_id else "весь план"
        logger.info("Plan %d (%s, comp_id=%d) -> очередь (размер: %d)",
                     plan_id, label, comp_id, self._queue.qsize())
        return True

    async def start(self) -> None:
        """Запускает поллер и воркер."""
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Воркер очереди запущен")

        if settings.qc_poll_enabled:
            self._poller_task = asyncio.create_task(self._poll_loop())
            logger.info("Поллер запущен (интервал: %d сек)", settings.qc_poll_interval_sec)
        else:
            logger.info("Поллер отключён (QC_POLL_ENABLED=false)")

    async def stop(self) -> None:
        """Останавливает поллер и воркер."""
        if self._poller_task:
            self._poller_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("Поллер и воркер остановлены")

    async def _poll_loop(self) -> None:
        """Цикл опроса Оки-Токи."""
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Ошибка при опросе Оки-Токи")

            await asyncio.sleep(settings.qc_poll_interval_sec)

    async def _poll_once(self) -> None:
        """Один цикл опроса — получает готовые планы и добавляет в очередь."""
        async with OkiTokiClient() as client:
            plans = await client.get_ready_plans()

        if not plans:
            logger.debug("Нет готовых планов")
            return

        added = 0
        for p in plans:
            if self.enqueue(p["comp_id"], p["plan_id"]):
                added += 1

        if added:
            logger.info("Добавлено %d планов в очередь из %d найденных", added, len(plans))

    async def _worker_loop(self) -> None:
        """Воркер — берёт задачи из очереди и обрабатывает по одной."""
        while True:
            try:
                task = await self._queue.get()
                self._current_task = task
                self._progress = RunProgress()

                try:
                    if task.session_id is not None:
                        # Один звонок (webhook от Вадима)
                        logger.info("Обработка звонка session_id=%d (plan=%d, comp=%d)",
                                    task.session_id, task.plan_id, task.comp_id)
                        result = await process_single_call(
                            task.comp_id, task.plan_id, task.session_id,
                        )
                        self._last_result = {
                            "comp_id": task.comp_id,
                            "plan_id": task.plan_id,
                            "session_id": task.session_id,
                            **result,
                        }
                    else:
                        # Весь план (ручной запуск или поллинг)
                        logger.info("Обработка плана %d (comp_id=%d)", task.plan_id, task.comp_id)
                        self._progress = RunProgress()
                        result = await run_plan(
                            task.plan_id,
                            comp_id=task.comp_id,
                            progress=self._progress,
                        )
                        self._last_result = {
                            "comp_id": task.comp_id,
                            "plan_id": task.plan_id,
                            **result,
                        }
                    logger.info("Задача завершена: %s", result)
                except Exception:
                    logger.exception("Ошибка при обработке задачи plan=%d", task.plan_id)
                    self._last_result = {
                        "comp_id": task.comp_id,
                        "plan_id": task.plan_id,
                        "error": "internal_error",
                    }
                finally:
                    self._active_plan_ids.discard(task.plan_id)
                    if task.session_id is not None:
                        self._active_calls.discard((task.comp_id, task.plan_id, task.session_id))
                    self._current_task = None
                    self._progress = None
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
