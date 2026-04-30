#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести валідації полів — 9 тестів.

Перевіряє 422 помилки при пропущених обов'язкових полях
для кожного з трьох POST-ендпоінтів.
"""
from config import run_test, print_result, VALID_HEADERS


def run_validation_tests() -> list:
    """Запустити всі тести валідації."""
    results = []

    # === /open — пропущені поля ===

    # 1. /open без session_id
    r = run_test(
        name="validation_open_no_session_id",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"comp_schema": "test_schema"},
    )
    print_result(r)
    results.append(r)

    # 2. /open без comp_schema
    r = run_test(
        name="validation_open_no_comp_schema",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": "test_session"},
    )
    print_result(r)
    results.append(r)

    # 3. /open порожнє тіло
    r = run_test(
        name="validation_open_empty_body",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={},
    )
    print_result(r)
    results.append(r)

    # === /generate — пропущені поля ===

    # 4. /generate без session_id
    r = run_test(
        name="validation_generate_no_session_id",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={"comp_schema": "test_schema", "text": "Тест"},
    )
    print_result(r)
    results.append(r)

    # 5. /generate без comp_schema
    r = run_test(
        name="validation_generate_no_comp_schema",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={"session_id": "test_session", "text": "Тест"},
    )
    print_result(r)
    results.append(r)

    # 6. /generate без text
    r = run_test(
        name="validation_generate_no_text",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={"session_id": "test_session", "comp_schema": "test_schema"},
    )
    print_result(r)
    results.append(r)

    # === /close — пропущені поля ===

    # 7. /close без session_id
    r = run_test(
        name="validation_close_no_session_id",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"comp_schema": "test_schema"},
    )
    print_result(r)
    results.append(r)

    # 8. /close без comp_schema
    r = run_test(
        name="validation_close_no_comp_schema",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": "test_session"},
    )
    print_result(r)
    results.append(r)

    # 9. /close порожнє тіло
    r = run_test(
        name="validation_close_empty_body",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={},
    )
    print_result(r)
    results.append(r)

    return results


if __name__ == "__main__":
    print("=== Test 02: Validation ===")
    run_validation_tests()
