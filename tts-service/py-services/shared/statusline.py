#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль statusline — отображение имени сервиса в ps/htop.

Использование:
    from shared.statusline import set_statusline
    set_statusline("translation-checker", port=8585)

В htop/ps будет видно:
    py-svc translation-checker|Running|port:8585
"""
import os
import time

try:
    from setproctitle import setproctitle
except ImportError:
    def setproctitle(title: str) -> None:  # noqa: ARG001
        pass  # setproctitle не установлен, пропускаем


_start_time = time.time()


def _format_uptime() -> str:
    """Форматирование uptime."""
    elapsed = int(time.time() - _start_time)
    days = elapsed // 86400
    hours = (elapsed % 86400) // 3600
    if days > 0:
        return f"{days}d_{hours}h"
    minutes = (elapsed % 3600) // 60
    return f"{hours}h_{minutes}m"


def set_statusline(service_name: str, port: int = 0, status: str = "Running") -> None:
    """Устанавливает имя процесса для отображения в ps/htop.

    Args:
        service_name: Имя сервиса.
        port: Порт сервиса.
        status: Текущий статус (Running, Starting, Stopping...).
    """
    pid = os.getpid()
    uptime = _format_uptime()
    parts = [f"py-svc {service_name}", status]
    if port:
        parts.append(f"port:{port}")
    parts.append(f"pid:{pid}")
    parts.append(f"uptime:{uptime}")
    title = "|".join(parts)
    setproctitle(title)


def update_statusline(service_name: str, port: int = 0, status: str = "Running") -> None:
    """Обновляет statusline (например, для обновления uptime)."""
    set_statusline(service_name, port, status)
