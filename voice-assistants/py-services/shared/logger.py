#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый модуль логирования для всех сервисов py-services.

Использование:
    from shared.logger import get_logger
    logger = get_logger("translation-checker")
    logger.info("Сообщение")  # → файл + stdout

    # С Discord-алертами (WARNING+ уходит в Discord):
    logger = get_logger("translation-checker", discord_webhook="https://discord.com/api/webhooks/...")
    logger.warning("Google TTS вернул 403")  # → файл + stdout + Discord
"""
import os
import sys
import time
import logging
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler

import requests

# Директория логов (по умолчанию /var/log/py-services/, можно переопределить через LOG_DIR)
LOG_DIR = Path(os.environ.get("LOG_DIR", "/var/log/py-services"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
DISCORD_RATE_LIMIT = 30  # секунд между одинаковыми сообщениями


class DiscordHandler(logging.Handler):
    """Logging handler, который отправляет WARNING+ сообщения в Discord webhook.

    Rate limit: не чаще 1 сообщения одного типа в 30 секунд.
    Отправка асинхронная (в отдельном потоке), чтобы не блокировать основной код.
    """

    COLOR_WARNING = 0xFFA500   # Оранжевый
    COLOR_ERROR = 0xFF0000     # Красный

    def __init__(self, webhook_url: str, service_name: str, rate_limit: int = DISCORD_RATE_LIMIT):
        super().__init__(level=logging.WARNING)
        self.webhook_url = webhook_url
        self.service_name = service_name
        self.rate_limit = rate_limit
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()
        self._hostname = self._get_hostname()

    @staticmethod
    def _get_hostname() -> str:
        import socket
        host_file = "/etc/host_hostname"
        if os.path.exists(host_file):
            with open(host_file, "r") as f:
                name = f.read().strip()
                if name:
                    return name
        return os.environ.get("HOST_HOSTNAME", socket.getfqdn())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg_key = f"{record.levelno}:{record.getMessage()[:100]}"

            with self._lock:
                now = time.time()
                last = self._last_sent.get(msg_key, 0)
                if now - last < self.rate_limit:
                    return
                self._last_sent[msg_key] = now

            thread = threading.Thread(target=self._send, args=(record,), daemon=True)
            thread.start()
        except Exception:
            self.handleError(record)

    def _send(self, record: logging.LogRecord) -> None:
        try:
            color = self.COLOR_ERROR if record.levelno >= logging.ERROR else self.COLOR_WARNING
            title = "ERROR" if record.levelno >= logging.ERROR else "WARNING"

            embed = {
                "title": title,
                "description": record.getMessage()[:2000],
                "color": color,
                "fields": [
                    {"name": "Service", "value": self.service_name},
                    {"name": "Server", "value": self._hostname},
                    {"name": "Level", "value": record.levelname, "inline": True},
                ],
            }

            requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10,
            )
        except Exception:
            pass


def get_logger(service_name: str, discord_webhook: str = "") -> logging.Logger:
    """Создаёт и возвращает логгер для сервиса.

    Args:
        service_name: Имя сервиса (например, "translation-checker").
        discord_webhook: Discord webhook URL. Если задан — WARNING+ сообщения
                         автоматически отправляются в Discord (rate limit 30с).

    Returns:
        Настроенный logging.Logger.
    """
    logger = logging.getLogger(f"py-svc.{service_name}")

    if logger.handlers:
        # Логгер уже инициализирован — но проверяем, нужно ли добавить DiscordHandler.
        # Это решает проблему порядка импортов: если tts_engine.py вызвал get_logger()
        # без discord_webhook раньше, чем server.py вызвал с discord_webhook.
        if discord_webhook:
            has_discord = any(isinstance(h, DiscordHandler) for h in logger.handlers)
            if not has_discord:
                discord_handler = DiscordHandler(
                    webhook_url=discord_webhook,
                    service_name=service_name,
                )
                logger.addHandler(discord_handler)
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(LOG_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (RotatingFileHandler)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{service_name}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except PermissionError:
        logger.warning(f"Нет прав на запись в {LOG_DIR}, логи только в stdout")

    # Discord handler (WARNING+)
    if discord_webhook:
        discord_handler = DiscordHandler(
            webhook_url=discord_webhook,
            service_name=service_name,
        )
        logger.addHandler(discord_handler)

    return logger
