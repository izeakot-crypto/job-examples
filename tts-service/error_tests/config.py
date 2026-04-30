#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфігурація та хелпери для тестування помилок TTS Google Chirp3 API.
"""
import os
import sys
import time
import json
import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://py-services.oki-toki.net/api/tts-google-chirp3"
API_KEY = os.environ.get("TGC_API_KEY", "_bHH8oJJ0G7CP1y1jsF3rFX0WJAYJaVNR3yuHC854vc")

VALID_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

VALID_OPEN_BODY = {
    "session_id": "error_test_session",
    "comp_schema": "test_schema",
}

VALID_GENERATE_BODY = {
    "session_id": "error_test_session",
    "comp_schema": "test_schema",
    "text": "Привіт, це тестовий запит.",
    "voice": "Leda",
    "locale": "uk_UA",
}

VALID_CLOSE_BODY = {
    "session_id": "error_test_session",
    "comp_schema": "test_schema",
}


def run_test(
    name: str,
    method: str,
    endpoint: str,
    headers: dict = None,
    body=None,
    content_type: str = None,
    raw_body: str = None,
    timeout: int = 30,
) -> dict:
    """
    Виконати один тестовий запит і повернути результат.

    Args:
        name: Назва тесту
        method: HTTP метод (GET, POST, PUT, DELETE)
        endpoint: Ендпоінт (наприклад, /open)
        headers: Заголовки запиту
        body: JSON тіло (dict)
        content_type: Override Content-Type
        raw_body: Сирий текст тіла (замість JSON)
        timeout: Таймаут у секундах

    Returns:
        dict з полями: name, method, url, status_code, response_body,
              response_headers, latency_ms, error (якщо є)
    """
    url = f"{BASE_URL}{endpoint}"
    result = {
        "name": name,
        "method": method.upper(),
        "url": url,
        "status_code": None,
        "response_body": None,
        "response_headers": {},
        "latency_ms": None,
        "error": None,
    }

    req_headers = dict(headers) if headers else {}
    if content_type:
        req_headers["Content-Type"] = content_type

    try:
        t0 = time.time()

        if raw_body is not None:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=req_headers,
                data=raw_body,
                timeout=timeout,
            )
        elif body is not None:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=req_headers,
                json=body,
                timeout=timeout,
            )
        else:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=req_headers,
                timeout=timeout,
            )

        latency_ms = int((time.time() - t0) * 1000)

        result["status_code"] = resp.status_code
        result["latency_ms"] = latency_ms
        result["response_headers"] = dict(resp.headers)

        try:
            result["response_body"] = resp.json()
        except (json.JSONDecodeError, ValueError):
            result["response_body"] = resp.text[:500] if resp.text else None

    except requests.exceptions.Timeout:
        result["error"] = "Request timeout"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {str(e)[:200]}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"

    return result


def print_result(result: dict):
    """Вивести результат тесту в консоль."""
    status = result["status_code"] or "ERROR"
    latency = f"{result['latency_ms']}ms" if result["latency_ms"] else "N/A"
    name = result["name"]

    if result["error"]:
        print(f"  [{status}] {name} — {latency} — ERROR: {result['error']}")
    else:
        body_preview = json.dumps(result["response_body"], ensure_ascii=False)
        if len(body_preview) > 120:
            body_preview = body_preview[:117] + "..."
        print(f"  [{status}] {name} — {latency} — {body_preview}")

