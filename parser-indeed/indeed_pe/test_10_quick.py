#!/usr/bin/env python3
"""Швидкий тест 10 вакансій - тільки пошук сайтів компаній"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import time
import random
from camoufox.sync_api import Camoufox

INDEED_DOMAIN = "pe.indeed.com"

def bypass_turnstile(page):
    for _ in range(15):
        time.sleep(1)
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                try:
                    bbox = frame.frame_element().bounding_box()
                    if bbox:
                        page.mouse.click(bbox['x'] + bbox['width']/9, bbox['y'] + bbox['height']/2)
                        break
                except: pass
    for _ in range(20):
        time.sleep(1)
        if 'un momento' not in (page.title() or "").lower():
            return True
    return False

def has_turnstile(page):
    if 'un momento' in (page.title() or "").lower():
        return True
    for frame in page.frames:
        if 'challenges.cloudflare.com' in frame.url:
            return True
    return False

print("="*60)
print("ШВИДКИЙ ТЕСТ: 10 вакансій - пошук сайтів компаній")
print("="*60)

with Camoufox(headless=True, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()

    # Прогрів
    page.goto("https://www.google.com.pe", timeout=30000)
    time.sleep(2)

    # Пошук
    print("\n[1] Завантаження пошуку...")
    page.goto(f"https://{INDEED_DOMAIN}/jobs?q=teleoperador&l=", timeout=60000)
    time.sleep(3)
    if has_turnstile(page):
        bypass_turnstile(page)
        time.sleep(3)

    # Збір вакансій
    vacancies = []
    for link in page.query_selector_all("a.jcs-JobTitle")[:10]:
        href = link.get_attribute("href")
        if href:
            url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
            vacancies.append(url)

    print(f"    Знайдено {len(vacancies)} вакансій")

    # Перевірка кожної
    results = []
    for idx, vac_url in enumerate(vacancies, 1):
        print(f"\n[{idx}/10] Вакансія...")

        page.goto(vac_url, timeout=60000)
        time.sleep(2)
        if has_turnstile(page):
            bypass_turnstile(page)
            time.sleep(2)

        # Компанія
        company_name = "?"
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            link = company_elem.query_selector("a")
            company_name = (link or company_elem).inner_text().strip()

        # URL компанії
        company_url = None
        company_link = page.query_selector("div[data-testid='inlineHeader-companyName'] a")
        if company_link:
            href = company_link.get_attribute("href")
            if href:
                company_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href

        website = None
        if company_url:
            page.goto(company_url, timeout=60000)
            time.sleep(2)
            if has_turnstile(page):
                bypass_turnstile(page)
                time.sleep(2)

            # Шукаємо сайт - різні селектори
            for sel in [
                'li[data-testid="companyInfo-companyWebsite"] a',
                '[data-testid*="Website"] a',
                'a[data-tn-element="companyWebsite"]',
            ]:
                elem = page.query_selector(sel)
                if elem:
                    website = elem.get_attribute("href")
                    break

            # Якщо не знайшли - шукаємо в тексті сторінки
            if not website:
                # Шукаємо блок "Sitio web" або зовнішні посилання
                all_links = page.query_selector_all("a[href^='http']")
                for link in all_links:
                    href = link.get_attribute("href") or ""
                    if href and "indeed" not in href and "hrtechprivacy" not in href:
                        # Перевіряємо чи це схоже на сайт компанії
                        text = link.inner_text().strip().lower()
                        if text and len(text) < 50:  # Короткий текст - можливо назва сайту
                            website = href
                            break

        status = "✓" if website else "✗"
        print(f"    {status} {company_name[:30]}: {website or 'сайт не знайдено'}")

        results.append({
            'company': company_name,
            'website': website
        })

    # Підсумок
    with_site = len([r for r in results if r['website']])
    print(f"\n{'='*60}")
    print(f"ПІДСУМОК: {with_site}/{len(results)} компаній мають сайт")
    print("="*60)

    if with_site > 0:
        print("\nКомпанії з сайтами:")
        for r in results:
            if r['website']:
                print(f"  - {r['company']}: {r['website']}")
