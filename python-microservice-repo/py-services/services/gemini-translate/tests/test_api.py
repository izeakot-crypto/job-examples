"""Tests for gemini-translate service."""
import os

import pytest
from fastapi.testclient import TestClient

# Set env BEFORE importing service
os.environ.setdefault("GT_API_KEY", "test_key_123")
os.environ.setdefault("GT_PORT", "8594")
os.environ.setdefault("GT_GEMINI_API_KEY", "test_gemini_key")
os.environ.setdefault("GT_GEMINI_MODEL", "gemini-2.5-pro")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")

from services.gemini_translate.server import app  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": "Bearer test_key_123"}


class TestHealth:
    def test_health_ok(self):
        r = client.get("/api/gemini-translate/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "gemini-translate"
        assert data["gemini_key_set"] is True

    def test_health_no_auth_required(self):
        r = client.get("/api/gemini-translate/health")
        assert r.status_code == 200


class TestAuth:
    def test_no_auth_returns_401(self):
        r = client.post(
            "/api/gemini-translate/translate",
            json={"lang": "de", "items": [{"original": "Hello", "translation": ""}]},
        )
        assert r.status_code == 401

    def test_wrong_token_returns_401(self):
        r = client.post(
            "/api/gemini-translate/translate",
            json={"lang": "de", "items": [{"original": "Hello", "translation": ""}]},
            headers={"Authorization": "Bearer wrong_key"},
        )
        assert r.status_code == 401


class TestValidation:
    def test_unknown_lang_returns_400(self):
        r = client.post(
            "/api/gemini-translate/translate",
            json={"lang": "xx", "items": [{"original": "Hello", "translation": ""}]},
            headers=AUTH,
        )
        assert r.status_code == 400
        assert "language code" in r.json()["detail"].lower()

    def test_empty_items_returns_400(self):
        r = client.post(
            "/api/gemini-translate/translate",
            json={"lang": "de", "items": []},
            headers=AUTH,
        )
        assert r.status_code == 400

    def test_skips_already_translated_items(self, monkeypatch):
        """Items with non-empty translation must be passed through without calling Gemini."""
        import services.gemini_translate.server as srv

        def mock_translate_batch(strings, target_lang, api_key, model, **kwargs):
            return [f"translated:{s}" for s in strings], []

        monkeypatch.setattr(srv, "translate_batch", mock_translate_batch)

        r = client.post(
            "/api/gemini-translate/translate",
            json={
                "lang": "de",
                "items": [
                    {"original": "Hello", "translation": "Hallo"},  # already translated — skip
                    {"original": "World", "translation": ""},  # needs translation
                ],
            },
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["skipped"] == 1
        assert data["translated"] == 1
        assert data["items"][0]["translation"] == "Hallo"
        assert data["items"][1]["translation"] == "translated:World"


class TestTranslate:
    def test_translate_success(self, monkeypatch):
        import services.gemini_translate.server as srv

        def mock_translate_batch(strings, target_lang, api_key, model, **kwargs):
            return [f"[{target_lang}] {s}" for s in strings], []

        monkeypatch.setattr(srv, "translate_batch", mock_translate_batch)

        r = client.post(
            "/api/gemini-translate/translate",
            json={
                "lang": "de",
                "items": [
                    {"original": "Ошибка выхода из PCP", "translation": ""},
                ],
            },
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["translated"] == 1
        assert data["skipped"] == 0
        assert data["items"][0]["translation"] == "[German] Ошибка выхода из PCP"
        assert data["validation_failures"] == []

    def test_translate_with_validation_failures(self, monkeypatch):
        import services.gemini_translate.server as srv

        def mock_translate_batch(strings, target_lang, api_key, model, **kwargs):
            translations = [s + " BAD" for s in strings]
            failures = [
                {
                    "id": 0,
                    "original": strings[0],
                    "translation": translations[0],
                    "error": "Format symbols mismatch",
                }
            ]
            return translations, failures

        monkeypatch.setattr(srv, "translate_batch", mock_translate_batch)

        r = client.post(
            "/api/gemini-translate/translate",
            json={
                "lang": "de",
                "items": [{"original": "Error %s occurred", "translation": ""}],
            },
            headers=AUTH,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["validation_failures"]) == 1
        assert data["validation_failures"][0]["index"] == 0

    def test_no_gemini_key_returns_503(self, monkeypatch):
        import services.gemini_translate.server as srv

        monkeypatch.setattr(srv, "GEMINI_API_KEY", "")

        r = client.post(
            "/api/gemini-translate/translate",
            json={"lang": "de", "items": [{"original": "Hello", "translation": ""}]},
            headers=AUTH,
        )
        assert r.status_code == 503
