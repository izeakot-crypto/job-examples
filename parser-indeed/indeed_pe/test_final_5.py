#!/usr/bin/env python3
"""Фінальний тест 5 вакансій з повним парсингом"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import re
import time
import random
from camoufox.sync_api import Camoufox
from urllib.parse import urljoin

INDEED_DOMAIN = "pe.indeed.com"
SEARCH_URL = f"https://{INDEED_DOMAIN}/jobs?q=Operador&l="  # Operador - більше великих компаній

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(?:\+51|51)?[\s.-]?9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}')

def has_turnstile(page):
    if 'un momento' in (page.title() or "").lower():
        return True
    for frame in page.frames:
        if 'challenges.cloudflare.com' in frame.url:
            return True
    return False

def bypass_turnstile(page):
    print("      [Turnstile]...", end=" ")
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
        if not has_turnstile(page):
            print("OK")
            return True
    print("FAIL")
    return False

def extract_contacts(page):
    emails, phones = set(), set()
    try:
        for link in page.query_selector_all("a[href^='mailto:']"):
            email = (link.get_attribute("href") or "").replace("mailto:", "").split("?")[0]
            if EMAIL_PATTERN.match(email) and 'indeed' not in email.lower():
                emails.add(email.lower())
        body = page.query_selector("body")
        if body:
            text = body.inner_text()
            for e in EMAIL_PATTERN.findall(text):
                if not any(x in e.lower() for x in ['indeed', 'example', '.png', '.jpg', 'sentry']):
                    emails.add(e.lower())
            for p in PHONE_PATTERN.findall(text):
                cleaned = re.sub(r'[^\d]', '', p)[-9:]
                if len(cleaned) == 9 and cleaned.startswith('9'):
                    phones.add(f"+51{cleaned}")
    except: pass
    return list(emails)[:3], list(phones)[:3]

def parse_website(page, url):
    print(f"      Парсинг сайту: {url[:40]}...")
    emails, phones = set(), set()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        if has_turnstile(page):
            bypass_turnstile(page)
            time.sleep(2)

        e, p = extract_contacts(page)
        emails.update(e)
        phones.update(p)

        # Контактні сторінки
        contact_urls = []
        for link in page.query_selector_all("a[href]")[:50]:
            href = link.get_attribute("href") or ""
            full = urljoin(url, href)
            if any(k in full.lower() for k in ['contact', 'contacto', 'about', 'nosotros']):
                if url.split('/')[2] in full and full not in contact_urls:
                    contact_urls.append(full)

        for cu in contact_urls[:2]:
            try:
                page.goto(cu, wait_until="domcontentloaded", timeout=20000)
                time.sleep(1)
                e, p = extract_contacts(page)
                emails.update(e)
                phones.update(p)
            except: pass
    except Exception as ex:
        print(f"      Помилка: {ex}")

    return list(emails)[:3], list(phones)[:3]

print("="*70)
print("ФІНАЛЬНИЙ ТЕСТ: 5 вакансій з повним парсингом")
print("="*70)

results = []
seen_companies = set()

with Camoufox(headless=True, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()
    page.set_default_timeout(60000)

    page.goto("https://www.google.com.pe", timeout=30000)
    time.sleep(2)

    print("\n[1] Завантаження пошуку...")
    page.goto(SEARCH_URL, timeout=60000)
    time.sleep(3)
    if has_turnstile(page):
        bypass_turnstile(page)
        time.sleep(3)

    vacancies = []
    for link in page.query_selector_all("a.jcs-JobTitle")[:15]:
        title = link.inner_text().strip()
        href = link.get_attribute("href")
        if href:
            url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
            vacancies.append({'title': title, 'url': url})

    print(f"    Знайдено {len(vacancies)} вакансій, обробляю до 5 унікальних компаній\n")

    count = 0
    for vac in vacancies:
        if count >= 5:
            break

        print(f"[Вакансія {count+1}] {vac['title'][:50]}...")

        page.goto(vac['url'], timeout=60000)
        time.sleep(2)
        if has_turnstile(page):
            bypass_turnstile(page)
            time.sleep(2)

        # Компанія
        company = ""
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            link = company_elem.query_selector("a")
            company = (link or company_elem).inner_text().strip()

        if not company or company.lower() in seen_companies:
            print(f"    Пропуск (дубль або без компанії)")
            continue
        seen_companies.add(company.lower())
        count += 1

        print(f"    Компанія: {company}")

        result = {
            'Компанія': company,
            'Сайт': '',
            'Email': '',
            'Телефон': '',
            'Вакансія': vac['url'],
            'Країна': 'PE'
        }

        # Сторінка компанії
        company_link = page.query_selector("div[data-testid='inlineHeader-companyName'] a")
        if company_link:
            href = company_link.get_attribute("href")
            if href:
                company_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
                print(f"    Сторінка компанії: {company_url[:50]}...")

                page.goto(company_url, timeout=60000)
                time.sleep(2)
                if has_turnstile(page):
                    bypass_turnstile(page)
                    time.sleep(2)

                # Сайт компанії
                website_elem = page.query_selector('li[data-testid="companyInfo-companyWebsite"] a')
                if website_elem:
                    website = website_elem.get_attribute("href")
                    if website and 'indeed' not in website:
                        result['Сайт'] = website
                        print(f"    ✓ Сайт: {website}")

                        emails, phones = parse_website(page, website)
                        result['Email'] = "; ".join(emails)
                        result['Телефон'] = "; ".join(phones)
                        print(f"    Email: {result['Email'] or '-'}")
                        print(f"    Телефон: {result['Телефон'] or '-'}")
                    else:
                        print(f"    ✗ Сайт не знайдено")
                else:
                    print(f"    ✗ Сайт не знайдено")
        else:
            print(f"    ✗ Посилання на компанію не знайдено")

        results.append(result)
        print()

# Результати
print("="*70)
print("РЕЗУЛЬТАТИ")
print("="*70)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['Компанія']}")
    print(f"   Сайт: {r['Сайт'] or '-'}")
    print(f"   Email: {r['Email'] or '-'}")
    print(f"   Телефон: {r['Телефон'] or '-'}")

with_site = len([r for r in results if r['Сайт']])
with_email = len([r for r in results if r['Email']])
with_phone = len([r for r in results if r['Телефон']])

print(f"\n{'='*70}")
print(f"СТАТИСТИКА:")
print(f"  Компаній: {len(results)}")
print(f"  З сайтом: {with_site} ({with_site/len(results)*100:.0f}%)" if results else "")
print(f"  З email: {with_email}")
print(f"  З телефоном: {with_phone}")
print("="*70)
