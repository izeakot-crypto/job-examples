import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CM_API_KEY", "test_key_123")
os.environ.setdefault("CM_PORT", "8592")
os.environ.setdefault("CM_ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("CM_ANTHROPIC_BASE_URL", "http://localhost:5003")
os.environ.setdefault("CM_YOUTUBE_API_KEY", "test-yt-key")
os.environ.setdefault("CM_GOOGLE_SA_FILE", "/tmp/fake-sa.json")
os.environ.setdefault("CM_SPREADSHEET_ID", "test-spreadsheet-id")
os.environ.setdefault("CM_COMPANIES_SPREADSHEET_ID", "test-companies-id")
os.environ.setdefault("LOG_DIR", "/tmp/py-services-test-logs")

from services.competitor_monitor.server import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test_key_123"}


class TestHealth:
    def test_health_ok(self):
        r = client.get("/api/competitor-monitor/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "competitor-monitor"
        assert "scheduler" in data

    def test_health_has_scheduler_info(self):
        r = client.get("/api/competitor-monitor/health")
        data = r.json()
        assert "cron" in data["scheduler"]
        assert "next_run" in data["scheduler"]


class TestAuth:
    def test_no_auth_401(self):
        r = client.post("/api/competitor-monitor/run")
        assert r.status_code in (401, 403)

    def test_valid_auth(self):
        r = client.post("/api/competitor-monitor/run", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
