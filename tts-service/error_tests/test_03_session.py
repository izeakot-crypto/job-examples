#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести сесій — 4 тести.

Перевіряє поведінку при неправильному порядку операцій з сесіями:
generate без open, close без open, double open, double close.
"""
import time
from config import run_test, print_result, VALID_HEADERS


def run_session_tests() -> list:
    """Запустити всі тести сесій."""
    results = []

    # 1. /generate без /open (сесія не існує)
    r = run_test(
        name="session_generate_without_open",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={
            "session_id": "nonexistent_session_xyz",
            "comp_schema": "test_schema",
            "text": "Тестовий текст",
            "voice": "Leda",
            "locale": "uk_UA",
        },
    )
    print_result(r)
    results.append(r)

    # 2. /close без /open (сесія не існує)
    r = run_test(
        name="session_close_without_open",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={
            "session_id": "nonexistent_session_xyz",
            "comp_schema": "test_schema",
        },
    )
    print_result(r)
    results.append(r)

    # 3. Double open (одна і та ж сесія двічі)
    unique_id = f"double_open_{int(time.time())}"
    r1 = run_test(
        name="session_double_open_first",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": unique_id, "comp_schema": "test_schema"},
    )
    print_result(r1)
    results.append(r1)

    r2 = run_test(
        name="session_double_open_second",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": unique_id, "comp_schema": "test_schema"},
    )
    print_result(r2)
    results.append(r2)

    # Прибираємо за собою
    run_test(
        name="_cleanup_double_open",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": unique_id, "comp_schema": "test_schema"},
    )

    # 4. Double close (закрити двічі)
    unique_id2 = f"double_close_{int(time.time())}"
    run_test(
        name="_setup_double_close",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": unique_id2, "comp_schema": "test_schema"},
    )

    r3 = run_test(
        name="session_double_close_first",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": unique_id2, "comp_schema": "test_schema"},
    )
    print_result(r3)
    results.append(r3)

    r4 = run_test(
        name="session_double_close_second",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": unique_id2, "comp_schema": "test_schema"},
    )
    print_result(r4)
    results.append(r4)

    return results


if __name__ == "__main__":
    print("=== Test 03: Session ===")
    run_session_tests()
