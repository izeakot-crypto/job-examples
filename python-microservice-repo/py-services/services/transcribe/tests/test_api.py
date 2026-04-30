#!/usr/bin/env python3
"""
Тести для Transcribe API.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

os.environ.setdefault("TR_API_KEY", "test-key-123")
os.environ.setdefault("TR_WHISPER_URL", "http://localhost:9000")
os.environ.setdefault("TR_REDIS_URL", "redis://localhost:6379/0")

from services.transcribe.server import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/transcribe/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "transcribe"


def test_add_task_no_auth():
    resp = client.post("/api/transcribe/add-task", json={
        "source_url": "http://example.com/audio.mp3",
        "locale": "uk",
        "callback_url": "http://example.com/callback",
    })
    assert resp.status_code == 401


def test_add_task_invalid_key():
    resp = client.post(
        "/api/transcribe/add-task",
        json={
            "source_url": "http://example.com/audio.mp3",
            "locale": "uk",
            "callback_url": "http://example.com/callback",
        },
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


def test_add_task_missing_callback():
    resp = client.post(
        "/api/transcribe/add-task",
        json={
            "source_url": "http://example.com/audio.mp3",
            "locale": "uk",
            "callback_url": "",
        },
        headers={"Authorization": "Bearer test-key-123"},
    )
    assert resp.status_code == 400


def test_add_task_success():
    with patch("services.transcribe.server.queue") as mock_queue:
        mock_queue.enqueue.return_value = "abc123"

        resp = client.post(
            "/api/transcribe/add-task",
            json={
                "source_url": "http://example.com/audio.mp3",
                "locale": "uk",
                "callback_url": "http://example.com/callback",
            },
            headers={"Authorization": "Bearer test-key-123"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "abc123"
