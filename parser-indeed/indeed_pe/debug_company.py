#!/usr/bin/env python3
"""Дебаг сторінки компанії"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import time
import random
from camoufox.sync_api import Camoufox
from pathlib import Path

INDEED_DOMAIN = "pe.indeed.com"

def check_for_turnstile(page):
    try:
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                return True
        if 'un momento' in (page.title() or "").lower():
            return True
        return False
    except:
        return False

def bypass_turnstile(page):
    for attempt in range(15):
        time.sleep(1)
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                try:
                    bbox = frame.frame_element().bounding_box()
                    if bbox:
                        x = bbox['x'] + bbox['width'] / 9
                        y = bbox['y'] + bbox['height'] / 2
                        page.mouse.click(x, y)
                        break
                except:
                    pass
    for i in range(20):
        time.sleep(1)
        if not check_for_turnstile(page):
            return True
    return False

with Camoufox(headless=True, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()

    # Прогрів
    page.goto("https://www.google.com.pe", timeout=30000)
    time.sleep(2)

    # Пошук
    print("Завантаження пошуку...")
    page.goto(f"https://{INDEED_DOMAIN}/jobs?q=teleoperador&l=", timeout=60000)
    time.sleep(3)

    if check_for_turnstile(page):
        print("Turnstile на пошуку...")
        bypass_turnstile(page)
        time.sleep(3)

    # Перша вакансія
    first_job = page.query_selector("a.jcs-JobTitle")
    if first_job:
        href = first_job.get_attribute("href")
        job_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
        print(f"Вакансія: {job_url[:70]}...")

        page.goto(job_url, timeout=60000)
        time.sleep(2)

        if check_for_turnstile(page):
            bypass_turnstile(page)
            time.sleep(2)

        # Компанія
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            print(f"Компанія: {company_elem.inner_text()}")

            # Посилання на компанію
            company_link = company_elem.query_selector("a")
            if company_link:
                company_href = company_link.get_attribute("href")
                company_url = f"https://{INDEED_DOMAIN}" + company_href if company_href.startswith("/") else company_href
                print(f"URL компанії: {company_url[:70]}...")

                # Переходимо на сторінку компанії
                page.goto(company_url, timeout=60000)
                time.sleep(3)

                if check_for_turnstile(page):
                    print("Turnstile на сторінці компанії...")
                    bypass_turnstile(page)
                    time.sleep(3)

                print(f"\nСторінка компанії завантажена:")
                print(f"URL: {page.url}")
                print(f"Title: {page.title()}")

                # Зберігаємо HTML
                Path("debug_results").mkdir(exist_ok=True)
                with open("debug_results/company_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                page.screenshot(path="debug_results/company_page.png")
                print("\nЗбережено: debug_results/company_page.html та .png")

                # Шукаємо сайт різними селекторами
                print("\n--- ПОШУК САЙТУ КОМПАНІЇ ---")

                selectors = [
                    'li[data-testid="companyInfo-companyWebsite"] a',
                    'a[data-testid="companyInfo-companyWebsite"]',
                    '[data-testid*="website"] a',
                    'a[href*="http"]:not([href*="indeed"])',
                    '.css-1lhpb9z a',  # можливий клас
                ]

                for sel in selectors:
                    elem = page.query_selector(sel)
                    if elem:
                        href = elem.get_attribute("href")
                        text = elem.inner_text()
                        print(f"  ✓ {sel}: {href or text}")
                    else:
                        print(f"  ✗ {sel}: не знайдено")

                # Всі посилання
                print("\n--- ВСІ ЗОВНІШНІ ПОСИЛАННЯ ---")
                for link in page.query_selector_all("a[href]")[:20]:
                    href = link.get_attribute("href") or ""
                    if href.startswith("http") and "indeed" not in href:
                        print(f"  {href[:60]}")

    page.close()
