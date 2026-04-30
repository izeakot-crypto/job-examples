#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальний тест pe.indeed.com
Перевіряє доступність та базовий парсинг
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import time
from camoufox.sync_api import Camoufox
from pathlib import Path
from datetime import datetime

TEST_URL = "https://pe.indeed.com/jobs?q=teleoperador&l="
HEADLESS_MODE = True  # Headless для швидкого тесту

def test_peru_indeed():
    print("="*70)
    print("ЛОКАЛЬНИЙ ТЕСТ: pe.indeed.com (Peru)")
    print("="*70)
    print(f"\nURL: {TEST_URL}")
    print(f"Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results_dir = Path("test_results")
    results_dir.mkdir(exist_ok=True)

    camoufox_params = {
        'headless': HEADLESS_MODE,
        'humanize': True,
        'os': 'windows',
        'locale': 'es-PE',
        'geoip': False,
    }

    print(f"[1/6] Запуск Camoufox (headless={HEADLESS_MODE})...")

    with Camoufox(**camoufox_params) as browser:
        page = browser.new_page()
        page.set_default_timeout(60000)

        # IP
        print(f"[2/6] Перевірка IP адреси...")
        try:
            page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            ip_text = page.inner_text("body")
            print(f"      IP: {ip_text}")
        except Exception as e:
            print(f"      Помилка отримання IP: {e}")

        # Прогрів
        print(f"[3/6] Прогрів браузера (google.com.pe)...")
        try:
            page.goto("https://www.google.com.pe", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            print(f"      OK")
        except Exception as e:
            print(f"      Помилка: {e}")

        # Indeed Peru
        print(f"[4/6] Перехід на pe.indeed.com...")
        try:
            page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)

            current_url = page.url
            page_title = page.title()

            print(f"      URL: {current_url[:80]}...")
            print(f"      Title: {page_title}")

        except Exception as e:
            print(f"      ПОМИЛКА переходу: {e}")
            return False

        # Аналіз
        print(f"[5/6] Аналіз сторінки...")

        blocked = False
        block_reason = ""

        if '__cf_chl_rt_tk=' in current_url:
            blocked = True
            block_reason = "Cloudflare Challenge в URL"

        if any(x in page_title.lower() for x in ['challenge', 'moment', 'verificación', 'un momento']):
            blocked = True
            block_reason = f"Challenge в заголовку: {page_title}"

        # Вакансії
        try:
            jobs_count = page.locator("a.jcs-JobTitle").count()
            print(f"      Знайдено вакансій (a.jcs-JobTitle): {jobs_count}")

            if jobs_count == 0:
                jobs_count_alt = page.locator("[data-testid='jobTitle']").count()
                print(f"      Альт. селектор [data-testid='jobTitle']: {jobs_count_alt}")

                if jobs_count_alt == 0:
                    body_text = page.inner_text("body")[:500].lower()
                    if 'captcha' in body_text or 'robot' in body_text or 'blocked' in body_text:
                        blocked = True
                        block_reason = "Captcha/Robot detection в тексті"
                    else:
                        print(f"      Текст сторінки (перші 300 символів):")
                        print(f"      {body_text[:300]}...")
        except Exception as e:
            print(f"      Помилка підрахунку вакансій: {e}")

        # Збереження
        print(f"[6/6] Збереження результатів...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        screenshot_path = results_dir / f"peru_test_{timestamp}.png"
        html_path = results_dir / f"peru_test_{timestamp}.html"

        page.screenshot(path=str(screenshot_path), full_page=False)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())

        print(f"      Screenshot: {screenshot_path}")
        print(f"      HTML: {html_path}")

        # Якщо є вакансії - виведемо перші 5
        if jobs_count > 0:
            print(f"\n[INFO] Перші вакансії:")
            for idx, link_elem in enumerate(page.query_selector_all("a.jcs-JobTitle")[:5], 1):
                title = link_elem.inner_text().strip()
                href = link_elem.get_attribute("href") or ""
                print(f"      {idx}. {title[:50]}...")

        # Результат
        print()
        print("="*70)
        if blocked:
            print(f"РЕЗУЛЬТАТ: ЗАБЛОКОВАНО")
            print(f"Причина: {block_reason}")
        elif jobs_count == 0:
            print(f"РЕЗУЛЬТАТ: СТОРІНКА ЗАВАНТАЖИЛАСЬ, АЛЕ ВАКАНСІЙ НЕ ЗНАЙДЕНО")
            print(f"Можливо потрібні cookies або інший селектор")
        else:
            print(f"РЕЗУЛЬТАТ: ДОСТУП Є!")
            print(f"Вакансій на сторінці: {jobs_count}")
        print("="*70)

        # Затримка для перегляду (тільки якщо видимий браузер)
        # if not HEADLESS_MODE:
        #     print("\nБраузер відкритий. Натисни Enter для закриття...")
        #     input()

        page.close()

        return not blocked and jobs_count > 0

if __name__ == "__main__":
    success = test_peru_indeed()
    sys.exit(0 if success else 1)
