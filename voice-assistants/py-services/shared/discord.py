#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый модуль Discord-нотификаций для всех сервисов py-services.

Использование:
    from shared.discord import DiscordNotifier
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/...")
    notifier.send_alert(title="Проблема", description="Описание", color=0xFF0000)
"""
import os
import socket
from datetime import datetime

import requests

from shared.logger import get_logger

logger = get_logger("discord")


def _get_hostname() -> str:
    """Получение hostname хоста (не контейнера)."""
    host_file = "/etc/host_hostname"
    if os.path.exists(host_file):
        with open(host_file, "r") as f:
            name = f.read().strip()
            if name:
                return name
    return os.environ.get("HOST_HOSTNAME", socket.getfqdn())


_HOSTNAME = _get_hostname()
_SCRIPT_PATH = os.environ.get("HOST_SCRIPT_PATH", os.path.abspath(__file__))


class DiscordNotifier:
    """Отправка уведомлений в Discord через webhook."""

    COLOR_ERROR = 0xFF0000      # Красный
    COLOR_WARNING = 0xFFA500    # Оранжевый
    COLOR_SUCCESS = 0x00FF00    # Зелёный
    COLOR_INFO = 0x0099FF       # Синий

    def __init__(self, webhook_url: str, service_name: str = "py-services"):
        self.webhook_url = webhook_url
        self.service_name = service_name

    def send_embed(
        self,
        title: str,
        description: str = "",
        color: int = COLOR_INFO,
        fields: list[dict] | None = None,
    ) -> bool:
        """Отправка embed-сообщения в Discord.

        Args:
            title: Заголовок embed.
            description: Описание.
            color: Цвет полоски (hex).
            fields: Дополнительные поля [{"name": "...", "value": "...", "inline": True}].

        Returns:
            True если отправлено успешно.
        """
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": fields or [],
            "footer": {
                "text": f"{self.service_name} | {_HOSTNAME}",
            },
        }

        # Добавляем информацию о сервере
        embed["fields"].extend([
            {"name": "Sender script", "value": _SCRIPT_PATH, "inline": False},
            {"name": "Server", "value": _HOSTNAME, "inline": True},
            {"name": "Service", "value": self.service_name, "inline": True},
        ])

        payload = {"embeds": [embed]}

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                logger.info(f"Discord: отправлено '{title}'")
                return True
            else:
                logger.error(f"Discord: ошибка {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Discord: ошибка отправки: {e}")
            return False

    def send_alert(self, title: str, description: str, fields: list[dict] | None = None) -> bool:
        """Отправка алерта (красный цвет)."""
        return self.send_embed(title, description, self.COLOR_ERROR, fields)

    def send_success(self, title: str, description: str = "") -> bool:
        """Отправка успешного уведомления (зелёный цвет)."""
        return self.send_embed(title, description, self.COLOR_SUCCESS)

    def send_warning(self, title: str, description: str = "") -> bool:
        """Отправка предупреждения (оранжевый цвет)."""
        return self.send_embed(title, description, self.COLOR_WARNING)
