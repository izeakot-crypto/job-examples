#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести локалей — 5 тестів.

Перевіряє поведінку API при невалідних або нестандартних локалях.
Потребує активну сесію — спершу відкриває, потім тестує, потім закриває.
"""
import time
from config import run_test, print_result, VALID_HEADERS


def run_locale_tests() -> list:
    """Запустити всі тести локалей."""
    results = []

    # Відкриваємо сесію для тестів
    session_id = f"locale_test_{int(time.time())}"
    comp_schema = "test_schema"

    setup = run_test(
        name="_setup_locale_session",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": session_id, "comp_schema": comp_schema},
    )

    if setup["status_code"] != 200:
        print(f"  WARN: Не вдалося відкрити сесію для тестів локалей: {setup}")
        return results

    base_body = {
        "session_id": session_id,
        "comp_schema": comp_schema,
        "text": "Тест",
        "voice": "Leda",
    }

    # 1. Непідтримувана locale — fr_FR
    r = run_test(
        name="locale_unsupported_fr_FR",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "locale": "fr_FR"},
    )
    print_result(r)
    results.append(r)

    # 2. Неіснуюча locale — xx_XX
    r = run_test(
        name="locale_nonexistent_xx_XX",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "locale": "xx_XX"},
    )
    print_result(r)
    results.append(r)

    # 3. Формат з дефісом — uk-UA (повинно нормалізуватись!)
    r = run_test(
        name="locale_dash_format_uk-UA",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "locale": "uk-UA"},
    )
    print_result(r)
    results.append(r)

    # 4. Невірний регістр — UK_ua
    r = run_test(
        name="locale_wrong_case_UK_ua",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "locale": "UK_ua"},
    )
    print_result(r)
    results.append(r)

    # 5. Порожня locale
    r = run_test(
        name="locale_empty",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "locale": ""},
    )
    print_result(r)
    results.append(r)

    # Закриваємо сесію
    run_test(
        name="_cleanup_locale_session",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": session_id, "comp_schema": comp_schema},
    )

    return results


if __name__ == "__main__":
    print("=== Test 04: Locale ===")
    run_locale_tests()
