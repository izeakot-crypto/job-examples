#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Головний runner — запускає всі тестові модулі та зберігає error_catalog.json.

Використання:
    cd error_tests
    python run_all_tests.py
"""
import os
import sys
import json
import time
from datetime import datetime

# Додаємо поточну директорію до sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BASE_URL
from test_01_auth import run_auth_tests
from test_02_validation import run_validation_tests
from test_03_session import run_session_tests
from test_04_locale import run_locale_tests
from test_05_text import run_text_tests
from test_06_content_type import run_content_type_tests
from test_07_edge_cases import run_edge_case_tests


def main():
    print(f"{'='*60}")
    print(f"TTS Google Chirp3-HD — Error Catalog Generator")
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    all_results = {}
    total_tests = 0
    t0 = time.time()

    # --- 1. Auth ---
    print("=== [1/7] Auth Tests ===")
    auth = run_auth_tests()
    all_results["01_auth"] = auth
    total_tests += len(auth)
    print()

    # --- 2. Validation ---
    print("=== [2/7] Validation Tests ===")
    validation = run_validation_tests()
    all_results["02_validation"] = validation
    total_tests += len(validation)
    print()

    # --- 3. Session ---
    print("=== [3/7] Session Tests ===")
    session = run_session_tests()
    all_results["03_session"] = session
    total_tests += len(session)
    print()

    # --- 4. Locale ---
    print("=== [4/7] Locale Tests ===")
    locale = run_locale_tests()
    all_results["04_locale"] = locale
    total_tests += len(locale)
    print()

    # --- 5. Text ---
    print("=== [5/7] Text Tests ===")
    text = run_text_tests()
    all_results["05_text"] = text
    total_tests += len(text)
    print()

    # --- 6. Content-Type ---
    print("=== [6/7] Content-Type Tests ===")
    content_type = run_content_type_tests()
    all_results["06_content_type"] = content_type
    total_tests += len(content_type)
    print()

    # --- 7. Edge Cases ---
    print("=== [7/7] Edge Case Tests ===")
    edge = run_edge_case_tests()
    all_results["07_edge_cases"] = edge
    total_tests += len(edge)
    print()

    elapsed = time.time() - t0

    # --- Збираємо error catalog ---
    error_catalog = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_tests": total_tests,
            "elapsed_sec": round(elapsed, 1),
        },
        "errors": {},
    }

    # Збираємо унікальні помилки по status_code
    for category, tests in all_results.items():
        for test in tests:
            # Пропускаємо внутрішні тести (починаються з _)
            if test["name"].startswith("_"):
                continue

            code = test["status_code"]
            if code is None:
                code = "network_error"

            code_str = str(code)
            if code_str not in error_catalog["errors"]:
                error_catalog["errors"][code_str] = []

            error_catalog["errors"][code_str].append({
                "test_name": test["name"],
                "category": category,
                "method": test["method"],
                "url": test["url"],
                "response_body": test["response_body"],
                "latency_ms": test["latency_ms"],
                "error": test["error"],
            })

    # --- Зберігаємо результат ---
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    catalog_path = os.path.join(results_dir, "error_catalog.json")

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(error_catalog, f, indent=2, ensure_ascii=False)

    # --- Підсумок ---
    print(f"{'='*60}")
    print(f"ПІДСУМОК")
    print(f"{'='*60}")
    print(f"Всього тестів: {total_tests}")
    print(f"Час: {elapsed:.1f}с")
    print()

    print("Помилки по HTTP-кодах:")
    for code in sorted(error_catalog["errors"].keys()):
        count = len(error_catalog["errors"][code])
        print(f"  {code}: {count} тестів")

    print(f"\nКаталог збережено: {catalog_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
