#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести Content-Type — 4 тести.

Перевіряє поведінку API при невірному Content-Type:
plain text, XML, порожнє тіло, зламаний JSON.
"""
import json
from config import run_test, print_result, API_KEY, VALID_OPEN_BODY


def run_content_type_tests() -> list:
    """Запустити всі тести Content-Type."""
    results = []

    auth_header = {"Authorization": f"Bearer {API_KEY}"}

    # 1. Content-Type: text/plain
    r = run_test(
        name="content_type_plain_text",
        method="POST",
        endpoint="/open",
        headers=auth_header,
        content_type="text/plain",
        raw_body=json.dumps(VALID_OPEN_BODY),
    )
    print_result(r)
    results.append(r)

    # 2. Content-Type: application/xml
    r = run_test(
        name="content_type_xml",
        method="POST",
        endpoint="/open",
        headers=auth_header,
        content_type="application/xml",
        raw_body="<request><session_id>test</session_id></request>",
    )
    print_result(r)
    results.append(r)

    # 3. Порожнє тіло (Content-Type: application/json)
    r = run_test(
        name="content_type_empty_body",
        method="POST",
        endpoint="/open",
        headers=auth_header,
        content_type="application/json",
        raw_body="",
    )
    print_result(r)
    results.append(r)

    # 4. Зламаний JSON
    r = run_test(
        name="content_type_malformed_json",
        method="POST",
        endpoint="/open",
        headers=auth_header,
        content_type="application/json",
        raw_body='{"session_id": "test", "comp_schema":',
    )
    print_result(r)
    results.append(r)

    return results


if __name__ == "__main__":
    print("=== Test 06: Content-Type ===")
    run_content_type_tests()
