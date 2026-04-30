"""Обязательные тесты сервиса quality-check: health, auth, basic func."""

import os

import pytest
from fastapi.testclient import TestClient

# Установка переменных ДО импорта app
os.environ.setdefault("QC_API_KEY", "test_key_123")
os.environ.setdefault("QC_PORT", "8591")
os.environ.setdefault("QC_OKI_TOKI_API_TOKEN", "test_token")
os.environ.setdefault("QC_OKI_TOKI_BASE_URL", "https://one.oki-toki.net")
os.environ.setdefault("QC_OKI_TOKI_COMP_ID", "1")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_API_KEY", "test")

from services.quality_check.server import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test_key_123"}


class TestHealth:
    """Health check доступен без авторизации."""

    def test_health_ok(self):
        r = client.get("/api/quality-check/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "quality-check"

    def test_health_has_version(self):
        r = client.get("/api/quality-check/health")
        assert "version" in r.json()


class TestAuth:
    """Защищённые эндпоинты требуют Bearer-токен."""

    def test_run_no_auth_returns_403(self):
        r = client.post("/api/quality-check/run", json={"comp_id": 1, "plan_id": 1})
        assert r.status_code in (401, 403)

    def test_status_no_auth_returns_403(self):
        r = client.get("/api/quality-check/status")
        assert r.status_code in (401, 403)

    def test_audit_no_auth_returns_403(self):
        r = client.get("/api/quality-check/audit", params={"comp_id": 1, "plan_id": 1, "session_id": 1})
        assert r.status_code in (401, 403)

    def test_run_wrong_key_returns_401(self):
        r = client.post(
            "/api/quality-check/run",
            json={"comp_id": 1, "plan_id": 1},
            headers={"Authorization": "Bearer wrong_key"},
        )
        assert r.status_code == 401


class TestEndpoints:
    """Базовые функциональные тесты."""

    def test_status_returns_idle(self):
        r = client.get("/api/quality-check/status", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert data["running"] is False

    def test_run_accepts_valid_request(self):
        """Проверяет что /run принимает запрос (реально не запускает LLM)."""
        r = client.post(
            "/api/quality-check/run",
            json={"comp_id": 1, "plan_id": 999},
            headers=AUTH,
        )
        # Может быть 200 (accepted) или ошибка API — но не 422/500
        assert r.status_code in (200, 409, 502)

    def test_run_missing_fields_returns_422(self):
        r = client.post(
            "/api/quality-check/run",
            json={},
            headers=AUTH,
        )
        assert r.status_code == 422

    def test_audit_not_found_returns_404(self):
        r = client.get(
            "/api/quality-check/audit",
            params={"comp_id": 999, "plan_id": 999, "session_id": 999},
            headers=AUTH,
        )
        assert r.status_code == 404
