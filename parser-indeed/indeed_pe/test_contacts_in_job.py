#!/usr/bin/env python3
"""Пошук контактів безпосередньо в описі вакансій"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import re
import time
from camoufox.sync_api import Camoufox

INDEED_DOMAIN = "pe.indeed.com"

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(?:\+51|51)?[\s.-]?9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}')
WHATSAPP_PATTERN = re.compile(r'(?:whatsapp|wsp|ws)[\s:]*[\+]?[\d\s.-]+', re.IGNORECASE)

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
print("ПОШУК КОНТАКТІВ В ОПИСІ ВАКАНСІЙ")
print("="*60)

with Camoufox(headless=True, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()

    page.goto("https://www.google.com.pe", timeout=30000)
    time.sleep(2)

    print("\n[1] Завантаження пошуку...")
    page.goto(f"https://{INDEED_DOMAIN}/jobs?q=teleoperador&l=", timeout=60000)
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

    print(f"    Знайдено {len(vacancies)} вакансій")

    results = []
    for idx, vac in enumerate(vacancies, 1):
        print(f"\n[{idx}/{len(vacancies)}] {vac['title'][:40]}...")

        page.goto(vac['url'], timeout=60000)
        time.sleep(2)
        if has_turnstile(page):
            bypass_turnstile(page)
            time.sleep(2)

        # Компанія
        company = "?"
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            link = company_elem.query_selector("a")
            company = (link or company_elem).inner_text().strip()

        # Опис вакансії
        description = ""
        desc_elem = page.query_selector("#jobDescriptionText")
        if desc_elem:
            description = desc_elem.inner_text()

        # Весь текст сторінки
        body = page.query_selector("body")
        full_text = body.inner_text() if body else ""

        # Пошук контактів
        emails = list(set(EMAIL_PATTERN.findall(full_text)))
        emails = [e for e in emails if not any(x in e.lower() for x in ['indeed', 'example', 'test', '.png', '.jpg'])]

        phones = list(set(PHONE_PATTERN.findall(full_text)))
        # Нормалізація
        normalized_phones = []
        for p in phones:
            cleaned = re.sub(r'[^\d]', '', p)
            if len(cleaned) >= 9:
                if not cleaned.startswith('51'):
                    cleaned = '51' + cleaned[-9:]
                normalized_phones.append(f"+{cleaned}")
        phones = list(set(normalized_phones))

        # WhatsApp
        whatsapp = WHATSAPP_PATTERN.findall(full_text)

        print(f"    Компанія: {company}")
        if emails:
            print(f"    Email: {', '.join(emails[:3])}")
        if phones:
            print(f"    Телефон: {', '.join(phones[:3])}")
        if whatsapp:
            print(f"    WhatsApp: {whatsapp[0][:30]}...")

        results.append({
            'company': company,
            'title': vac['title'],
            'emails': emails[:3],
            'phones': phones[:3],
            'url': vac['url']
        })

    # Підсумок
    with_email = len([r for r in results if r['emails']])
    with_phone = len([r for r in results if r['phones']])

    print(f"\n{'='*60}")
    print(f"ПІДСУМОК:")
    print(f"  Вакансій: {len(results)}")
    print(f"  З email: {with_email}")
    print(f"  З телефоном: {with_phone}")
    print("="*60)

    if with_email or with_phone:
        print("\nЗнайдені контакти:")
        for r in results:
            if r['emails'] or r['phones']:
                print(f"\n  {r['company']}:")
                if r['emails']:
                    print(f"    Email: {', '.join(r['emails'])}")
                if r['phones']:
                    print(f"    Тел: {', '.join(r['phones'])}")
