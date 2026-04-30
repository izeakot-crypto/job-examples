#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести авторизації — 6 тестів.

Перевіряє поведінку API при різних проблемах з авторизацією:
без заголовка, невірний ключ, без Bearer, порожній ключ, status/health без auth.
"""
from config import run_test, print_result, BASE_URL, API_KEY, VALID_OPEN_BODY


def run_auth_tests() -> list:
    """Запустити всі тести авторизації."""
    results = []

    # 1. Без Authorization header
    r = run_test(
        name="auth_no_header",
        method="POST",
        endpoint="/open",
        headers={"Content-Type": "application/json"},
        body=VALID_OPEN_BODY,
    )
    print_result(r)
    results.append(r)

    # 2. Невірний API ключ
    r = run_test(
        name="auth_wrong_key",
        method="POST",
        endpoint="/open",
        headers={
            "Authorization": "Bearer wrong_key_12345",
            "Content-Type": "application/json",
        },
        body=VALID_OPEN_BODY,
    )
    print_result(r)
    results.append(r)

    # 3. Без префіксу Bearer (просто ключ)
    r = run_test(
        name="auth_no_bearer_prefix",
        method="POST",
        endpoint="/open",
        headers={
            "Authorization": API_KEY,
            "Content-Type": "application/json",
        },
        body=VALID_OPEN_BODY,
    )
    print_result(r)
    results.append(r)

    # 4. Порожній Bearer token
    r = run_test(
        name="auth_empty_bearer",
        method="POST",
        endpoint="/open",
        headers={
            "Authorization": "Bearer ",
            "Content-Type": "application/json",
        },
        body=VALID_OPEN_BODY,
    )
    print_result(r)
    results.append(r)

    # 5. GET /status без авторизації
    r = run_test(
        name="auth_status_no_auth",
        method="GET",
        endpoint="/status",
        headers={},
    )
    print_result(r)
    results.append(r)

    # 6. GET /health без авторизації (має працювати!)
    r = run_test(
        name="auth_health_no_auth",
        method="GET",
        endpoint="/health",
        headers={},
    )
    print_result(r)
    results.append(r)

    return results


if __name__ == "__main__":
    print("=== Test 01: Auth ===")
    run_auth_tests()
