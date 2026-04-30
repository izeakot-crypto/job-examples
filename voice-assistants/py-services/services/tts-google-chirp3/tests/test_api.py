#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести для TTS Google Chirp3-HD API.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Встановлюємо env-змінні ДО імпорту
os.environ.setdefault("TGC_API_KEY", "test_key_123")
os.environ.setdefault("TGC_PORT", "8589")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")
os.environ.setdefault("TGC_CACHE_DIR", "/tmp/py-services-test-tts-cache")

# Мокаємо google.cloud.texttospeech щоб тести не потребували credentials
mock_tts = MagicMock()
with patch.dict("sys.modules", {"google.cloud.texttospeech": mock_tts, "google.cloud": MagicMock()}):
    from services.tts_google_chirp3.server import app

client = TestClient(app)
AUTH_HEADER = {"Authorization": "Bearer test_key_123"}


class TestHealthEndpoint:
    """Тести health check."""

    def test_health_returns_ok(self):
        response = client.get("/api/tts-google-chirp3/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "tts-google-chirp3"

    def test_health_no_auth_required(self):
        response = client.get("/api/tts-google-chirp3/health")
        assert response.status_code == 200


class TestAuthEndpoint:
    """Тести авторизації."""

    def test_open_without_auth_rejected(self):
        response = client.post(
            "/api/tts-google-chirp3/open",
            json={"session_id": "test", "comp_schema": "billing"}
        )
        assert response.status_code in (401, 403)

    def test_open_with_wrong_key_returns_401(self):
        response = client.post(
            "/api/tts-google-chirp3/open",
            json={"session_id": "test", "comp_schema": "billing"},
            headers={"Authorization": "Bearer wrong_key"}
        )
        assert response.status_code == 401

    def test_status_without_auth_rejected(self):
        response = client.get("/api/tts-google-chirp3/status")
        assert response.status_code in (401, 403)


class TestOpenEndpoint:
    """Тести відкриття сесії."""

    def test_open_with_valid_key(self):
        response = client.post(
            "/api/tts-google-chirp3/open",
            json={"session_id": "test_sess", "comp_schema": "bill_1"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["session_id"] == "test_sess"
        assert data["comp_schema"] == "bill_1"
        assert "voices" in data

    def test_open_missing_session_id(self):
        response = client.post(
            "/api/tts-google-chirp3/open",
            json={"comp_schema": "bill"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422


class TestCloseEndpoint:
    """Тести закриття сесії."""

    def test_close_nonexistent_session(self):
        response = client.post(
            "/api/tts-google-chirp3/close",
            json={"session_id": "nonexistent", "comp_schema": "bill"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 404


class TestGenerateEndpoint:
    """Тести генерації."""

    def test_generate_without_session_returns_400(self):
        response = client.post(
            "/api/tts-google-chirp3/generate",
            json={
                "session_id": "no_such",
                "comp_schema": "bill",
                "text": "Test text",
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 400

    def test_generate_invalid_locale_returns_400(self):
        # Спершу відкриваємо сесію
        client.post(
            "/api/tts-google-chirp3/open",
            json={"session_id": "loc_test", "comp_schema": "bill"},
            headers=AUTH_HEADER,
        )
        response = client.post(
            "/api/tts-google-chirp3/generate",
            json={
                "session_id": "loc_test",
                "comp_schema": "bill",
                "text": "Bonjour",
                "locale": "fr_FR",
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 400
