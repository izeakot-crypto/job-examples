#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест доступності br.indeed.com через Camoufox
Перевіряє чи не блокує IP
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import os
import platform
import time

# КРИТИЧНО: Включаємо Software WebGL на Linux серверах БЕЗ GPU
if platform.system() == "Linux":
    os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
    os.environ['GALLIUM_DRIVER'] = 'llvmpipe'
    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    print("[WEBGL] Software rendering enabled")

from camoufox.sync_api import Camoufox
from pathlib import Path
from datetime import datetime

# URL для тесту
TEST_URL = "https://br.indeed.com/jobs?q=teleoperador&l="
HEADLESS_MODE = True

def test_brazil_indeed():
    print("="*80)
    print("ТЕСТ ДОСТУПНОСТІ br.indeed.com")
    print("="*80)
    print(f"\nURL: {TEST_URL}")
    print(f"Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results_dir = Path("test_brazil_results")
    results_dir.mkdir(exist_ok=True)

    camoufox_params = {
        'headless': False if platform.system() == "Linux" else HEADLESS_MODE,
        'humanize': True,
        'os': 'windows',
        'locale': 'pt-BR',  # Бразильська локаль
        'geoip': False,
    }

    print(f"[1/5] Запуск Camoufox...")

    with Camoufox(**camoufox_params) as browser:
        page = browser.new_page()
        page.set_default_timeout(60000)

        # Отримуємо IP
        print(f"[2/5] Перевірка IP адреси...")
        try:
            page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            ip_text = page.inner_text("body")
            print(f"      IP: {ip_text}")
        except Exception as e:
            print(f"      Помилка отримання IP: {e}")

        # Переходимо на Indeed Brazil
        print(f"[3/5] Перехід на br.indeed.com...")
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

        # Перевіряємо на блокування
        print(f"[4/5] Аналіз сторінки...")

        blocked = False
        block_reason = ""

        # Cloudflare Challenge
        if '__cf_chl_rt_tk=' in current_url:
            blocked = True
            block_reason = "Cloudflare Challenge в URL"

        # Turnstile / Captcha
        if 'challenge' in page_title.lower() or 'moment' in page_title.lower() or 'verificação' in page_title.lower():
            blocked = True
            block_reason = f"Challenge в заголовку: {page_title}"

        # Перевіряємо наявність вакансій
        try:
            jobs_count = page.locator("a.jcs-JobTitle").count()
            print(f"      Знайдено вакансій: {jobs_count}")

            if jobs_count == 0:
                # Можливо інший селектор для Бразилії
                jobs_count_alt = page.locator("[data-testid='jobTitle']").count()
                print(f"      Альт. селектор: {jobs_count_alt}")

                if jobs_count_alt == 0:
                    # Перевіряємо чи є хоч якийсь контент
                    body_text = page.inner_text("body")[:500]
                    if 'captcha' in body_text.lower() or 'robot' in body_text.lower():
                        blocked = True
                        block_reason = "Captcha/Robot detection"
        except Exception as e:
            print(f"      Помилка підрахунку вакансій: {e}")

        # Зберігаємо скріншот та HTML
        print(f"[5/5] Збереження результатів...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        screenshot_path = results_dir / f"brazil_test_{timestamp}.png"
        html_path = results_dir / f"brazil_test_{timestamp}.html"

        page.screenshot(path=str(screenshot_path), full_page=False)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())

        print(f"      Screenshot: {screenshot_path}")
        print(f"      HTML: {html_path}")

        # Результат
        print()
        print("="*80)
        if blocked:
            print(f"РЕЗУЛЬТАТ: ЗАБЛОКОВАНО")
            print(f"Причина: {block_reason}")
        else:
            print(f"РЕЗУЛЬТАТ: ДОСТУП Є")
            print(f"Вакансій на сторінці: {jobs_count}")
        print("="*80)

        page.close()

        return not blocked

if __name__ == "__main__":
    success = test_brazil_indeed()
    sys.exit(0 if success else 1)
