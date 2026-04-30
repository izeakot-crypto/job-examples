#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести edge cases — 4 тести.

Перевіряє граничні випадки: невірні HTTP-методи, неіснуючі ендпоінти,
надто довгий session_id.
"""
from config import run_test, print_result, VALID_HEADERS, VALID_OPEN_BODY


def run_edge_case_tests() -> list:
    """Запустити всі edge case тести."""
    results = []

    # 1. GET на POST-ендпоінт (/open)
    r = run_test(
        name="edge_get_on_post_endpoint",
        method="GET",
        endpoint="/open",
        headers=VALID_HEADERS,
    )
    print_result(r)
    results.append(r)

    # 2. POST на GET-ендпоінт (/status)
    r = run_test(
        name="edge_post_on_get_endpoint",
        method="POST",
        endpoint="/status",
        headers=VALID_HEADERS,
        body={"test": "data"},
    )
    print_result(r)
    results.append(r)

    # 3. Неіснуючий ендпоінт
    r = run_test(
        name="edge_nonexistent_endpoint",
        method="GET",
        endpoint="/nonexistent",
        headers=VALID_HEADERS,
    )
    print_result(r)
    results.append(r)

    # 4. Дуже довгий session_id (1000 символів)
    r = run_test(
        name="edge_long_session_id",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": "x" * 1000, "comp_schema": "test_schema"},
    )
    print_result(r)
    results.append(r)

    # Прибираємо за собою якщо сесія створилась
    if r["status_code"] == 200:
        run_test(
            name="_cleanup_long_session",
            method="POST",
            endpoint="/close",
            headers=VALID_HEADERS,
            body={"session_id": "x" * 1000, "comp_schema": "test_schema"},
        )

    return results


if __name__ == "__main__":
    print("=== Test 07: Edge Cases ===")
    run_edge_case_tests()
