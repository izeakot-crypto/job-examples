#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест з обходом Turnstile для pe.indeed.com
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import time
import random
from camoufox.sync_api import Camoufox
from pathlib import Path
from datetime import datetime

TEST_URL = "https://pe.indeed.com/jobs?q=teleoperador&l="
HEADLESS_MODE = True


def check_for_turnstile(page):
    """Перевірка активного Turnstile"""
    try:
        widget = page.query_selector("div[data-sitekey], div.cf-turnstile, #cf-turnstile-container")
        if widget:
            bbox = widget.bounding_box()
            if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                return True

        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                try:
                    elem = frame.frame_element()
                    bbox = elem.bounding_box()
                    if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                        return True
                except:
                    pass

        title = (page.title() or "").lower()
        if 'just a moment' in title or 'challenge' in title or 'un momento' in title:
            return True

        return False
    except:
        return False


def bypass_turnstile(page, context=""):
    """Обхід Cloudflare Turnstile"""
    print(f"  [Turnstile] Спроба обходу ({context})...")

    clicked = False

    for attempt in range(15):
        time.sleep(1)

        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                print(f"  [Turnstile] Знайдено iframe після {attempt+1}с")

                try:
                    frame_element = frame.frame_element()
                    bounding_box = frame_element.bounding_box()

                    if bounding_box and bounding_box['width'] > 0 and bounding_box['height'] > 0:
                        coord_x = bounding_box['x']
                        coord_y = bounding_box['y']
                        width = bounding_box['width']
                        height = bounding_box['height']

                        checkbox_x = coord_x + width / 9 + random.uniform(-2, 2)
                        checkbox_y = coord_y + height / 2 + random.uniform(-2, 2)

                        print(f"  [Turnstile] Bbox: x={coord_x:.0f}, y={coord_y:.0f}, w={width:.0f}, h={height:.0f}")
                        print(f"  [Turnstile] Клік по: ({checkbox_x:.0f}, {checkbox_y:.0f})")

                        # Рух миші
                        start_x = random.randint(100, 800)
                        start_y = random.randint(100, 400)
                        page.mouse.move(start_x, start_y)
                        time.sleep(random.uniform(0.1, 0.3))

                        mid_x = (start_x + checkbox_x) / 2 + random.uniform(-20, 20)
                        mid_y = (start_y + checkbox_y) / 2 + random.uniform(-20, 20)
                        page.mouse.move(mid_x, mid_y)
                        time.sleep(random.uniform(0.15, 0.35))

                        page.mouse.move(checkbox_x, checkbox_y)
                        time.sleep(random.uniform(0.3, 0.6))

                        page.mouse.click(checkbox_x, checkbox_y)
                        clicked = True
                        print(f"  [Turnstile] Клік виконано!")

                        time.sleep(random.uniform(0.5, 1.0))
                        break

                except Exception as e:
                    print(f"  [Turnstile] Помилка кліку: {e}")

        if clicked:
            break

    if not clicked:
        print(f"  [Turnstile] Iframe не знайдено за 15с!")
        return False

    print(f"  [Turnstile] Очікування рішення...")
    for i in range(30):
        time.sleep(1)

        if not check_for_turnstile(page):
            print(f"  [Turnstile] ✓ Вирішено за {i+1}с!")
            time.sleep(5)
            return True

        if i % 5 == 0 and i > 0:
            print(f"  [Turnstile] Очікування... {i}/30с")

    print(f"  [Turnstile] ✗ Timeout (30с)")
    return False


def test_peru_with_turnstile():
    print("="*70)
    print("ТЕСТ З ОБХОДОМ TURNSTILE: pe.indeed.com")
    print("="*70)
    print(f"\nURL: {TEST_URL}")
    print(f"Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results_dir = Path("test_results")
    results_dir.mkdir(exist_ok=True)

    with Camoufox(headless=HEADLESS_MODE, humanize=True, os='windows', locale='es-PE', geoip=False) as browser:
        page = browser.new_page()
        page.set_default_timeout(60000)

        # IP
        print(f"[1/5] Перевірка IP...")
        try:
            page.goto("https://api.ipify.org?format=json", timeout=30000)
            time.sleep(2)
            print(f"      IP: {page.inner_text('body')}")
        except Exception as e:
            print(f"      Помилка: {e}")

        # Прогрів
        print(f"[2/5] Прогрів браузера...")
        page.goto("https://www.google.com.pe", timeout=30000)
        time.sleep(2)

        # Indeed
        print(f"[3/5] Перехід на pe.indeed.com...")
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        print(f"      URL: {page.url[:70]}...")
        print(f"      Title: {page.title()}")

        # Turnstile?
        print(f"[4/5] Перевірка Turnstile...")
        if check_for_turnstile(page):
            print(f"      Turnstile виявлено! Спроба обходу...")

            if bypass_turnstile(page, "peru_test"):
                print(f"      ✓ Turnstile пройдено!")
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                time.sleep(3)
            else:
                print(f"      ✗ Не вдалося обійти Turnstile")
        else:
            print(f"      Turnstile не виявлено")

        # Результат
        print(f"[5/5] Фінальна перевірка...")
        current_url = page.url
        title = page.title()

        print(f"      URL: {current_url[:70]}...")
        print(f"      Title: {title}")

        jobs_count = page.locator("a.jcs-JobTitle").count()
        print(f"      Вакансій: {jobs_count}")

        # Скріншот
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = results_dir / f"peru_turnstile_{timestamp}.png"
        html_path = results_dir / f"peru_turnstile_{timestamp}.html"

        page.screenshot(path=str(screenshot_path), full_page=False)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())

        print(f"      Screenshot: {screenshot_path}")

        # Якщо є вакансії
        if jobs_count > 0:
            print(f"\n[INFO] Перші вакансії:")
            for idx, link_elem in enumerate(page.query_selector_all("a.jcs-JobTitle")[:5], 1):
                title = link_elem.inner_text().strip()
                print(f"      {idx}. {title[:50]}...")

        print()
        print("="*70)
        if jobs_count > 0:
            print(f"РЕЗУЛЬТАТ: УСПІХ! Знайдено {jobs_count} вакансій")
        elif 'indeed.com/jobs' in current_url and 'cf_chl' not in current_url:
            print(f"РЕЗУЛЬТАТ: Сторінка завантажилась, але вакансій 0")
        else:
            print(f"РЕЗУЛЬТАТ: НЕ ВДАЛОСЯ - все ще заблоковано")
        print("="*70)

        page.close()

        return jobs_count > 0


if __name__ == "__main__":
    success = test_peru_with_turnstile()
    sys.exit(0 if success else 1)
