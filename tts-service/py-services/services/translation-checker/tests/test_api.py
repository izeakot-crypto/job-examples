#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для Translation Checker API.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Устанавливаем минимальные env-переменные для тестов
os.environ.setdefault("TC_API_KEY", "test_key_123")
os.environ.setdefault("TC_PORT", "8585")
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")

from services.translation_checker.server import app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer test_key_123"}


class TestHealthEndpoint:
    """Тесты health check."""

    def test_health_returns_ok(self):
        response = client.get("/api/translation-checker/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "translation-checker"

    def test_health_no_auth_required(self):
        response = client.get("/api/translation-checker/health")
        assert response.status_code == 200


class TestAuthEndpoint:
    """Тесты авторизации."""

    def test_check_without_auth_rejected(self):
        response = client.post(
            "/api/translation-checker/check",
            json={"items": []}
        )
        assert response.status_code in (401, 403)

    def test_check_with_wrong_key_returns_401(self):
        response = client.post(
            "/api/translation-checker/check",
            json={"items": []},
            headers={"Authorization": "Bearer wrong_key"}
        )
        assert response.status_code == 401

    def test_check_with_valid_key_returns_200(self):
        response = client.post(
            "/api/translation-checker/check",
            json={"items": []},
            headers=AUTH_HEADER
        )
        assert response.status_code == 200


class TestCheckEndpoint:
    """Тесты основного эндпоинта."""

    def test_empty_items_accepted(self):
        response = client.post(
            "/api/translation-checker/check",
            json={"items": []},
            headers=AUTH_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["total_items"] == 0

    def test_valid_items_accepted(self):
        response = client.post(
            "/api/translation-checker/check",
            json={
                "items": [
                    {
                        "Оригинал": "Сохранить",
                        "EN": "Save",
                        "UA": "Зберегти"
                    }
                ]
            },
            headers=AUTH_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["total_items"] == 1

    def test_invalid_json_returns_error(self):
        response = client.post(
            "/api/translation-checker/check",
            content="not a json",
            headers={**AUTH_HEADER, "Content-Type": "application/json"}
        )
        assert response.status_code in (400, 422)


class TestCheckFileEndpoint:
    """Тесты загрузки файлов."""

    def test_upload_csv_file(self):
        csv_content = "Оригинал,EN,UA\nСохранить,Save,Зберегти\n"
        response = client.post(
            "/api/translation-checker/check-file",
            headers=AUTH_HEADER,
            files={"file": ("test.csv", csv_content, "text/csv")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["total_items"] == 1

    def test_upload_json_file(self):
        json_content = '{"items": [{"Оригинал": "Тест", "EN": "Test"}]}'
        response = client.post(
            "/api/translation-checker/check-file",
            headers=AUTH_HEADER,
            files={"file": ("test.json", json_content, "application/json")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["total_items"] == 1

    def test_upload_without_auth_rejected(self):
        response = client.post(
            "/api/translation-checker/check-file",
            files={"file": ("test.csv", "data", "text/csv")}
        )
        assert response.status_code in (401, 403)
