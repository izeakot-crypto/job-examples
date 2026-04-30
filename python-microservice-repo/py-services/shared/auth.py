#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый модуль авторизации для всех сервисов py-services.

Использование:
    from shared.auth import require_auth

    API_KEY = os.environ.get("TC_API_KEY", "")

    @app.post("/api/my-service/check", dependencies=[Depends(require_auth(API_KEY))])
    async def check(body: CheckRequest):
        ...

В Swagger UI автоматически появится кнопка "Authorize" с полем для Bearer-токена.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()


def require_auth(api_key: str):
    """Фабрика FastAPI Dependency для проверки Bearer-токена.

    Args:
        api_key: Ожидаемый API-ключ.

    Returns:
        FastAPI Dependency, которая проверяет Authorization header
        и интегрируется со Swagger UI (кнопка "Authorize").
    """
    def verify(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
        if credentials.credentials != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return verify
