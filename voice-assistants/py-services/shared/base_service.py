#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Базовый модуль для создания FastAPI-сервисов.

Использование:
    from shared.base_service import create_app, run_service

    app = create_app(
        service_name="translation-checker",
        title="Translation Checker API",
        description="Проверка качества переводов",
        version="2.0.0",
    )

    # Добавляем свои эндпоинты (авторизация через Depends)
    @app.post(f"/api/translation-checker/check", dependencies=[Depends(require_auth(API_KEY))])
    async def check(body: CheckRequest):
        ...

    # Запуск
    if __name__ == "__main__":
        run_service(app, port=8585, service_name="translation-checker")
"""
import os
import logging

from fastapi import FastAPI
import uvicorn

from shared.statusline import set_statusline
from shared.logger import get_logger


def create_app(
    service_name: str,
    title: str = "",
    description: str = "",
    version: str = "1.0.0",
    include_health: bool = True,
) -> FastAPI:
    """Создаёт стандартный FastAPI app с health-эндпоинтом и Swagger UI.

    Args:
        service_name: Имя сервиса (используется в URL: /api/{service_name}/...).
        title: Название для Swagger UI.
        description: Описание для Swagger UI.
        version: Версия API.
        include_health: Регистрировать базовый /health (False если сервис добавит свой).

    Returns:
        Настроенный FastAPI app.
    """
    container_role = os.environ.get("CONTAINER_ROLE", "prod")

    effective_title = title or f"{service_name} API"
    if container_role == "test":
        effective_title = f"[TEST] {effective_title}"

    # root_path НЕ используем — Gateway сам переписывает /test/ → /api/,
    # поэтому внутри контейнера все URL остаются /api/...
    app = FastAPI(
        title=effective_title,
        description=description,
        version=version,
        docs_url=f"/api/{service_name}/docs",
        redoc_url=f"/api/{service_name}/redoc",
        openapi_url=f"/api/{service_name}/openapi.json",
    )

    logger = get_logger(service_name)

    if include_health:
        @app.get(f"/api/{service_name}/health")
        async def health():
            """Health check — без авторизации."""
            return {
                "status": "ok",
                "service": service_name,
                "version": version,
                "environment": container_role,
            }

    @app.on_event("startup")
    async def startup():
        logger.info("=" * 60)
        logger.info(f"SERVICE: {service_name} v{version} [{container_role.upper()}]")
        logger.info("=" * 60)

    return app


def run_service(app: FastAPI, port: int, service_name: str) -> None:
    """Запуск сервиса с uvicorn и установкой statusline.

    Args:
        app: FastAPI приложение.
        port: Порт для прослушивания.
        service_name: Имя сервиса (для statusline).
    """
    set_statusline(service_name, port=port, status="Starting")

    logger = get_logger(service_name)
    logger.info(f"Запуск {service_name} на порту {port}")

    set_statusline(service_name, port=port, status="Running")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )
