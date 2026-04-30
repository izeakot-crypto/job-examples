#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for LIRA Assistants API.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("LA_API_KEY", "test_key_123")
os.environ.setdefault("LA_PORT", "8590")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")

from fastapi.testclient import TestClient
from services.lira_assistants_api.server import app, sessions

client = TestClient(app)
AUTH_HEADER = {"Authorization": "Bearer test_key_123"}


class TestHealthEndpoint:
    """Health check tests."""

    def test_health_returns_ok(self):
        response = client.get("/api/lira-assistants-api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "lira-assistants-api"

    def test_health_no_auth_required(self):
        response = client.get("/api/lira-assistants-api/health")
        assert response.status_code == 200


class TestAuthEndpoint:
    """Authorization tests."""

    def test_create_without_auth_rejected(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-1",
                "comp_id": 1,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
        )
        assert response.status_code in (401, 403)

    def test_create_with_wrong_key_returns_401(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-1",
                "comp_id": 1,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers={"Authorization": "Bearer wrong_key"},
        )
        assert response.status_code == 401

    def test_message_without_auth_rejected(self):
        response = client.post(
            "/api/lira-assistants-api/message",
            json={
                "comp_id": 1,
                "assistant_session_id": "fake",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert response.status_code in (401, 403)


class TestCreateEndpoint:
    """Create session tests."""

    def test_create_missing_fields_returns_422(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={"session_id": "call-1"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422

    def test_create_invalid_provider_returns_422(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-1",
                "comp_id": 1,
                "contact_id": 100,
                "provider": "unknown_provider",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 422

    @patch("services.lira_assistants_api.session.get_provider")
    def test_create_openai_success(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat", "model": "gpt-4o"})
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-100",
                "comp_id": 42,
                "contact_id": 7890,
                "provider": "openai",
                "config": {
                    "api_key": "sk-test-key",
                    "model": "gpt-4o",
                    "system_prompt": "You are a helpful assistant.",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert "assistant_session_id" in data
        assert len(data["assistant_session_id"]) == 36  # UUID format

    @patch("services.lira_assistants_api.session.get_provider")
    def test_create_claude_success(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"model": "claude-sonnet-4-20250514"})
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-200",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "claude",
                "config": {"api_key": "sk-ant-test"},
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert "assistant_session_id" in data

    def test_create_n8n_without_url_returns_400(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-300",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "n8n",
                "config": {"api_key": "test"},
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "reason" in data["error"]


class TestResumeEndpoint:
    """Resume session tests."""

    def test_resume_nonexistent_returns_404(self):
        response = client.post(
            "/api/lira-assistants-api/resume",
            json={
                "comp_id": 42,
                "assistant_session_id": "nonexistent-session-id",
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "reason" in data["error"]

    @patch("services.lira_assistants_api.session.get_provider")
    def test_resume_success(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat"})
        mock_get_provider.return_value = mock_provider

        # Create session first
        create_resp = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-resume",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        session_id = create_resp.json()["assistant_session_id"]

        # Resume
        response = client.post(
            "/api/lira-assistants-api/resume",
            json={"comp_id": 42, "assistant_session_id": session_id},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assistant_session_id"] == session_id

    @patch("services.lira_assistants_api.session.get_provider")
    def test_resume_wrong_comp_id_returns_403(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat"})
        mock_get_provider.return_value = mock_provider

        create_resp = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-compid",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        session_id = create_resp.json()["assistant_session_id"]

        response = client.post(
            "/api/lira-assistants-api/resume",
            json={"comp_id": 999, "assistant_session_id": session_id},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 403


class TestMessageEndpoint:
    """Message endpoint tests."""

    def test_message_nonexistent_session_returns_404(self):
        response = client.post(
            "/api/lira-assistants-api/message",
            json={
                "comp_id": 42,
                "assistant_session_id": "nonexistent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 404

    @patch("services.lira_assistants_api.session.get_provider")
    def test_message_success(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat"})

        from services.lira_assistants_api.models import Completion
        mock_provider.send_message = AsyncMock(
            return_value=Completion(text="Hello! How can I help?", tokens_send=10, tokens_received=8)
        )
        mock_get_provider.return_value = mock_provider

        # Create
        create_resp = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-msg",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        session_id = create_resp.json()["assistant_session_id"]

        # Message
        response = client.post(
            "/api/lira-assistants-api/message",
            json={
                "comp_id": 42,
                "assistant_session_id": session_id,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data
        assert data["completion"]["text"] == "Hello! How can I help?"
        assert data["completion"]["tokens_send"] == 10
        assert data["completion"]["tokens_received"] == 8


class TestCloseEndpoint:
    """Close session tests."""

    def test_close_nonexistent_returns_404(self):
        response = client.post(
            "/api/lira-assistants-api/close",
            json={"comp_id": 42, "assistant_session_id": "nonexistent"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 404

    @patch("services.lira_assistants_api.session.get_provider")
    def test_close_success(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat"})
        mock_provider.close_session = AsyncMock(return_value=None)
        mock_get_provider.return_value = mock_provider

        # Create
        create_resp = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-close",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        session_id = create_resp.json()["assistant_session_id"]

        # Close
        response = client.post(
            "/api/lira-assistants-api/close",
            json={"comp_id": 42, "assistant_session_id": session_id},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "closed"

    @patch("services.lira_assistants_api.session.get_provider")
    def test_close_double_returns_404(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.create_session = AsyncMock(return_value={"mode": "chat"})
        mock_provider.close_session = AsyncMock(return_value=None)
        mock_get_provider.return_value = mock_provider

        # Create
        create_resp = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-dblclose",
                "comp_id": 42,
                "contact_id": 100,
                "provider": "openai",
                "config": {"api_key": "sk-test"},
            },
            headers=AUTH_HEADER,
        )
        session_id = create_resp.json()["assistant_session_id"]

        # Close first time
        client.post(
            "/api/lira-assistants-api/close",
            json={"comp_id": 42, "assistant_session_id": session_id},
            headers=AUTH_HEADER,
        )

        # Close second time
        response = client.post(
            "/api/lira-assistants-api/close",
            json={"comp_id": 42, "assistant_session_id": session_id},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 404


class TestErrorResponseFormat:
    """Verify error responses match spec format: {"error": {"reason": "..."}}."""

    def test_404_has_correct_format(self):
        response = client.post(
            "/api/lira-assistants-api/resume",
            json={"comp_id": 1, "assistant_session_id": "nonexistent"},
            headers=AUTH_HEADER,
        )
        data = response.json()
        assert "error" in data
        assert "reason" in data["error"]
        assert isinstance(data["error"]["reason"], str)

    def test_n8n_400_has_correct_format(self):
        response = client.post(
            "/api/lira-assistants-api/create",
            json={
                "session_id": "call-err",
                "comp_id": 1,
                "contact_id": 100,
                "provider": "n8n",
                "config": {"api_key": "test"},
            },
            headers=AUTH_HEADER,
        )
        data = response.json()
        assert "error" in data
        assert "reason" in data["error"]
