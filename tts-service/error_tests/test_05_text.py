#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести тексту — 7 тестів.

Перевіряє поведінку API з різним вмістом тексту:
довгий текст, XSS, емоджі, пробіли, один символ, числа.
Потребує активну сесію.
"""
import time
from config import run_test, print_result, VALID_HEADERS


def run_text_tests() -> list:
    """Запустити всі тести тексту."""
    results = []

    # Відкриваємо сесію для тестів
    session_id = f"text_test_{int(time.time())}"
    comp_schema = "test_schema"

    setup = run_test(
        name="_setup_text_session",
        method="POST",
        endpoint="/open",
        headers=VALID_HEADERS,
        body={"session_id": session_id, "comp_schema": comp_schema},
    )

    if setup["status_code"] != 200:
        print(f"  WARN: Не вдалося відкрити сесію: {setup}")
        return results

    base_body = {
        "session_id": session_id,
        "comp_schema": comp_schema,
        "voice": "Leda",
        "locale": "uk_UA",
    }

    # 1. Довгий текст — 1000 символів
    r = run_test(
        name="text_1000_chars",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "Це тестове речення для перевірки. " * 30},
    )
    print_result(r)
    results.append(r)

    # 2. Дуже довгий текст — 5000 символів
    r = run_test(
        name="text_5000_chars",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "Довгий текст для стрес-тесту API. " * 145},
        timeout=60,
    )
    print_result(r)
    results.append(r)

    # 3. XSS payload
    r = run_test(
        name="text_xss_payload",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": '<script>alert("XSS")</script>'},
    )
    print_result(r)
    results.append(r)

    # 4. Емоджі
    r = run_test(
        name="text_emoji",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "Привіт! 😀🎉🔥 Як справи?"},
    )
    print_result(r)
    results.append(r)

    # 5. Тільки пробіли (має бути помилка — min_length=1 але пробіли є символами)
    r = run_test(
        name="text_only_spaces",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "     "},
    )
    print_result(r)
    results.append(r)

    # 6. Один символ
    r = run_test(
        name="text_single_char",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "А"},
    )
    print_result(r)
    results.append(r)

    # 7. Тільки числа
    r = run_test(
        name="text_numbers_only",
        method="POST",
        endpoint="/generate",
        headers=VALID_HEADERS,
        body={**base_body, "text": "1234567890"},
    )
    print_result(r)
    results.append(r)

    # Закриваємо сесію
    run_test(
        name="_cleanup_text_session",
        method="POST",
        endpoint="/close",
        headers=VALID_HEADERS,
        body={"session_id": session_id, "comp_schema": comp_schema},
    )

    return results


if __name__ == "__main__":
    print("=== Test 05: Text ===")
    run_text_tests()
