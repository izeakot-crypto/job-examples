#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест парсингу 3 вакансій для pe.indeed.com
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import re
import time
import random
from camoufox.sync_api import Camoufox
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

INDEED_DOMAIN = "pe.indeed.com"
TEST_URL = f"https://{INDEED_DOMAIN}/jobs?q=teleoperador&l="
HEADLESS_MODE = True
MAX_VACANCIES = 3

# Регулярки
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(?:\+51|0051|51)?[\s.-]?(?:9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|\d{1,2}[\s.-]?\d{3}[\s.-]?\d{4})')


def normalize_peru_phone(phone_str):
    """Нормалізація перуанського телефону"""
    if not phone_str:
        return None
    cleaned = re.sub(r'[^\d+]', '', phone_str)
    if cleaned.startswith('+51'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0051'):
        cleaned = cleaned[4:]
    elif cleaned.startswith('51') and len(cleaned) > 9:
        cleaned = cleaned[2:]
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    if len(cleaned) == 9 and cleaned.startswith('9'):
        pass
    elif len(cleaned) == 8:
        pass
    else:
        return None
    if len(set(cleaned)) < 4:
        return None
    return f"+51{cleaned}"


def check_for_turnstile(page):
    """Перевірка Turnstile"""
    try:
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
        if 'un momento' in title or 'challenge' in title:
            return True
        return False
    except:
        return False


def bypass_turnstile(page, context=""):
    """Обхід Turnstile"""
    print(f"    [Turnstile] Обхід ({context})...")
    clicked = False

    for attempt in range(15):
        time.sleep(1)
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                try:
                    frame_element = frame.frame_element()
                    bbox = frame_element.bounding_box()
                    if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                        checkbox_x = bbox['x'] + bbox['width'] / 9 + random.uniform(-2, 2)
                        checkbox_y = bbox['y'] + bbox['height'] / 2 + random.uniform(-2, 2)

                        page.mouse.move(random.randint(100, 500), random.randint(100, 300))
                        time.sleep(0.2)
                        page.mouse.move(checkbox_x, checkbox_y)
                        time.sleep(0.3)
                        page.mouse.click(checkbox_x, checkbox_y)
                        clicked = True
                        print(f"    [Turnstile] Клік виконано!")
                        break
                except Exception as e:
                    print(f"    [Turnstile] Помилка: {e}")
        if clicked:
            break

    if not clicked:
        return False

    for i in range(30):
        time.sleep(1)
        if not check_for_turnstile(page):
            print(f"    [Turnstile] ✓ Вирішено за {i+1}с!")
            time.sleep(3)
            return True
    return False


def extract_emails(page):
    """Витягнути emails"""
    emails = set()
    try:
        for link in page.query_selector_all("a[href^='mailto:']"):
            href = link.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0].strip()
            if EMAIL_PATTERN.match(email):
                emails.add(email.lower())
        body = page.query_selector("body")
        if body:
            text = body.inner_text()
            for email in EMAIL_PATTERN.findall(text):
                if not any(x in email.lower() for x in ['.png', '.jpg', '.css', '.js', 'example.com', 'sentry']):
                    emails.add(email.lower())
    except:
        pass
    return list(emails)[:3]


def extract_phones(page):
    """Витягнути телефони"""
    phones = set()
    try:
        for link in page.query_selector_all("a[href^='tel:']"):
            href = link.get_attribute("href") or ""
            phone = href.replace("tel:", "").strip()
            normalized = normalize_peru_phone(phone)
            if normalized:
                phones.add(normalized)
        body = page.query_selector("body")
        if body:
            text = body.inner_text()
            for phone in PHONE_PATTERN.findall(text):
                normalized = normalize_peru_phone(phone)
                if normalized:
                    phones.add(normalized)
    except:
        pass
    return list(phones)[:3]


def get_company_website(page, company_indeed_url):
    """Отримати сайт компанії з Indeed"""
    if not company_indeed_url:
        return None
    try:
        page.goto(company_indeed_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        if check_for_turnstile(page):
            if not bypass_turnstile(page, "company"):
                return None
            time.sleep(2)
        website_elem = page.query_selector('li[data-testid="companyInfo-companyWebsite"] a')
        if website_elem:
            url = website_elem.get_attribute("href")
            if url and url.startswith("http") and 'indeed.com' not in url:
                return url
    except Exception as e:
        print(f"    Помилка: {e}")
    return None


def parse_company_website(page, website_url):
    """Парсинг сайту компанії"""
    try:
        page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        if check_for_turnstile(page):
            bypass_turnstile(page, "website")
            time.sleep(2)
        emails = extract_emails(page)
        phones = extract_phones(page)

        # Контактні сторінки
        contact_urls = []
        for link in page.query_selector_all("a[href]")[:100]:
            href = link.get_attribute("href") or ""
            full_url = urljoin(website_url, href)
            if any(kw in full_url.lower() for kw in ['contact', 'contacto', 'about', 'nosotros']):
                if full_url not in contact_urls and website_url.split('/')[2] in full_url:
                    contact_urls.append(full_url)

        for url in contact_urls[:3]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(1)
                emails.extend(extract_emails(page))
                phones.extend(extract_phones(page))
            except:
                pass

        return {
            "emails": list(set(emails))[:3],
            "phones": list(set(phones))[:3]
        }
    except Exception as e:
        print(f"    Помилка парсингу сайту: {e}")
        return {"emails": [], "phones": []}


def test_3_vacancies():
    print("="*70)
    print(f"ТЕСТ ПАРСИНГУ {MAX_VACANCIES} ВАКАНСІЙ: pe.indeed.com")
    print("="*70)
    print(f"Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = []

    with Camoufox(headless=HEADLESS_MODE, humanize=True, os='windows', locale='es-PE', geoip=False) as browser:
        page = browser.new_page()
        page.set_default_timeout(60000)

        # IP
        print("[1] Перевірка IP...")
        page.goto("https://api.ipify.org?format=json", timeout=30000)
        time.sleep(1)
        print(f"    IP: {page.inner_text('body')}")

        # Прогрів
        print("[2] Прогрів...")
        page.goto("https://www.google.com.pe", timeout=30000)
        time.sleep(2)

        # Indeed
        print("[3] Завантаження pe.indeed.com...")
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        if check_for_turnstile(page):
            print("    Turnstile виявлено...")
            bypass_turnstile(page, "search")
            time.sleep(3)

        # Вакансії
        print("[4] Збір вакансій...")
        vacancy_links = []
        for link_elem in page.query_selector_all("a.jcs-JobTitle")[:MAX_VACANCIES]:
            title = link_elem.inner_text().strip()
            href = link_elem.get_attribute("href")
            if href:
                full_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
                vacancy_links.append({'title': title, 'url': full_url})

        print(f"    Знайдено: {len(vacancy_links)} вакансій\n")

        # Парсинг кожної вакансії
        for idx, vac in enumerate(vacancy_links, 1):
            print(f"[Вакансія {idx}/{len(vacancy_links)}] {'-'*50}")
            print(f"  Назва: {vac['title'][:50]}...")

            result = {
                'Компания': '',
                'Телефон': '',
                'Сайт': '',
                'Email': '',
                'Ссылка на вакансию': vac['url'],
                'Страна': 'PE'
            }

            # Відкриваємо вакансію
            page.goto(vac['url'], wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            if check_for_turnstile(page):
                bypass_turnstile(page, f"vacancy_{idx}")
                time.sleep(2)

            # Компанія
            company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
            if company_elem:
                company_link = company_elem.query_selector("a")
                if company_link:
                    result['Компания'] = company_link.inner_text().strip()
                else:
                    result['Компания'] = company_elem.inner_text().strip()

            print(f"  Компанія: {result['Компания']}")

            # Сторінка компанії на Indeed
            company_indeed_url = None
            company_link = page.query_selector('div[data-testid="inlineHeader-companyName"] a')
            if company_link:
                href = company_link.get_attribute("href")
                if href:
                    company_indeed_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href

            # Сайт компанії
            if company_indeed_url:
                print(f"  Шукаю сайт компанії...")
                website = get_company_website(page, company_indeed_url)
                if website:
                    result['Сайт'] = website
                    print(f"  Сайт: {website[:50]}...")

                    # Парсимо сайт
                    print(f"  Парсинг сайту...")
                    contacts = parse_company_website(page, website)
                    result['Email'] = "; ".join(contacts['emails']) if contacts['emails'] else ''
                    result['Телефон'] = "; ".join(contacts['phones']) if contacts['phones'] else ''
                else:
                    print(f"  Сайт не знайдено")

            print(f"  Email: {result['Email'] or '-'}")
            print(f"  Телефон: {result['Телефон'] or '-'}")
            print()

            results.append(result)
            time.sleep(1)

        page.close()

    # Результати
    print("="*70)
    print("РЕЗУЛЬТАТИ")
    print("="*70)

    for idx, r in enumerate(results, 1):
        print(f"\n{idx}. {r['Компания']}")
        print(f"   Сайт: {r['Сайт'] or '-'}")
        print(f"   Email: {r['Email'] or '-'}")
        print(f"   Телефон: {r['Телефон'] or '-'}")

    # Статистика
    with_site = len([r for r in results if r['Сайт']])
    with_email = len([r for r in results if r['Email']])
    with_phone = len([r for r in results if r['Телефон']])

    print(f"\n{'='*70}")
    print(f"СТАТИСТИКА:")
    print(f"  Всього вакансій: {len(results)}")
    print(f"  З сайтом: {with_site}")
    print(f"  З email: {with_email}")
    print(f"  З телефоном: {with_phone}")
    print("="*70)

    return results


if __name__ == "__main__":
    test_3_vacancies()
