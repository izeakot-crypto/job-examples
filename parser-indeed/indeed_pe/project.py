#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indeed Parser v5.0 - Peru (pe.indeed.com)

Парсер для перуанського Indeed по запросу "teleoperador"

Простая логика:
1. Собираем ссылки на вакансии с Indeed Peru
2. Открываем каждую вакансию
3. Извлекаем: название, компанию, email, телефон, сайт компании
4. Если есть сайт - переходим туда и ищем контакты (mailto в contact/about)
5. Сохраняем: Компания | Вакансия | Email | Телефон | Сайт | Ссылка на вакансию

Turnstile bypass: проверяем ТОЛЬКО активный виджет (не просто упоминание в HTML)
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import os
import platform

# КРИТИЧНО: Включаем Software WebGL на Linux серверах БЕЗ GPU
if platform.system() == "Linux":
    os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
    os.environ['GALLIUM_DRIVER'] = 'llvmpipe'
    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    print("[WEBGL] Software rendering enabled (Mesa llvmpipe) - WebGL will work without GPU!")

import re
import time
import logging
import random
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from camoufox.sync_api import Camoufox
import pandas as pd
from openpyxl import load_workbook
import sys
sys.path.append(str(Path(__file__).parent.parent))
from webhook import send_webhook, WEBHOOK_START_URL, WEBHOOK_RESULTS_URL
import pytz
from flareprox_helper import FlareProxHelper
from cookies_helper import load_cookies_from_json, apply_cookies_to_context
from webshare_proxy import WebshareProxyManager, load_webshare_config
from network_logger import NetworkLogger


# ================== КОНФИГУРАЦИЯ ==================

INDEED_DOMAIN = "pe.indeed.com"
# Два пошукові запити
SEARCH_QUERIES = ["Operador", "teleoperador"]
PAGES_PER_QUERY = 5  # 5 сторінок на кожен запит = 10 всього
PAGES_TO_PARSE = 10  # Загальна кількість сторінок
HEADLESS_MODE = True  # True - headless режим, False - видимый браузер
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# ================== НАСТРОЙКА ПРОКСИ ==================

USE_PROXIES = False  # Отключено: работаем напрямую
PROXY_CONFIG_FILE = "webshare_config.json"

proxy_manager = None
proxy_config = None

if USE_PROXIES:
    try:
        ws_config = load_webshare_config(PROXY_CONFIG_FILE)
        proxy_manager = WebshareProxyManager(
            api_key=ws_config['api_key'],
            mode=ws_config.get('mode', 'direct'),
            country_codes=ws_config.get('country_codes', []),
            check_health=ws_config.get('check_health', False),
            health_timeout=ws_config.get('health_timeout', 10),
            preferred_protocol=ws_config.get('preferred_protocol', 'http')
        )
        if proxy_manager.get_proxy_count() > 0:
            logging.info(f"Прокси включён: всего {proxy_manager.get_proxy_count()} прокси")
        else:
            USE_PROXIES = False
            proxy_manager = None
    except FileNotFoundError:
        USE_PROXIES = False
        proxy_manager = None
    except Exception as e:
        USE_PROXIES = False
        proxy_manager = None

# Регулярки
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Перуанські телефони: +51, мобільні починаються з 9 (9 цифр)
# Стаціонарні: код міста (1-2 цифри) + номер
PHONE_PATTERN = re.compile(r'(?:\+51|0051|51)?[\s.-]?(?:9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|\d{1,2}[\s.-]?\d{3}[\s.-]?\d{4})')


def normalize_peru_phone(phone_str):
    """
    Нормализация и валидация перуанского телефона

    Правила Peru:
    - Мобильные: начинаются с 9, всего 9 цифр (например: 987 654 321)
    - Стационарные: код города (1-2 цифры) + 7 цифр (например: 01 234 5678 для Lima)
    - Код страны: +51

    Возвращает: нормализованный телефон в формате +51XXXXXXXXX или None если невалиден
    """
    if not phone_str:
        return None

    # Очистка от всех символов кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone_str)

    # Убираем код страны если есть
    if cleaned.startswith('+51'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0051'):
        cleaned = cleaned[4:]
    elif cleaned.startswith('51') and len(cleaned) > 9:
        cleaned = cleaned[2:]

    # Убираем ведущий 0 (код выхода на межгород)
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]

    # Мобильные - 9 цифр, начинаются с 9
    if len(cleaned) == 9 and cleaned.startswith('9'):
        pass  # OK
    # Стационарные Lima - 8 цифр (1 + 7)
    elif len(cleaned) == 8 and cleaned.startswith('1'):
        cleaned = cleaned  # OK
    # Стационарные другие города - 8 цифр
    elif len(cleaned) == 8:
        pass  # OK
    else:
        return None

    # Исключаем одинаковые цифры
    if len(set(cleaned)) == 1:
        return None

    # Исключаем простые последовательности
    if cleaned in ['123456789', '987654321', '012345678']:
        return None

    # Исключаем номера с 4+ повторяющимися цифрами подряд
    for i in range(len(cleaned) - 3):
        if len(set(cleaned[i:i+4])) == 1:
            return None

    # Минимум 4 уникальных цифры
    if len(set(cleaned)) < 4:
        return None

    # Возвращаем нормализованный формат
    return f"+51{cleaned}"


# Результаты
kiev_tz = pytz.timezone('Europe/Kiev')
current_time = datetime.now(kiev_tz).strftime("%Y-%m-%d_%H-%M-%S")
results_dir = Path(f"results_{current_time}")
results_dir.mkdir(exist_ok=True)

# Логирование
log_file = results_dir / f"parser_log_{current_time}.txt"

root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ],
    force=True
)

logging.getLogger().setLevel(logging.DEBUG)

logging.info("="*80)
logging.info(f"Лог файл создан: {log_file}")
logging.info("="*80)


# Глобальный менеджер ротации
proxy_rotation_manager = None


# ================== TURNSTILE BYPASS ==================

def check_for_turnstile(page):
    """Проверка АКТИВНОГО Turnstile (не просто упоминания в HTML!)"""
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

        page_text = page.inner_text("body").lower() if page.query_selector("body") else ""
        if 'verificación' in page_text or 'verificacion' in page_text:
            has_cf_iframe = False
            for frame in page.frames:
                if 'challenges.cloudflare.com' in frame.url:
                    try:
                        elem = frame.frame_element()
                        bbox = elem.bounding_box()
                        if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                            has_cf_iframe = True
                            break
                    except:
                        pass

            if has_cf_iframe:
                return True

        return False
    except:
        return False


def bypass_turnstile(page, context=""):
    """Обход Cloudflare Turnstile"""
    logging.info(f"  [Turnstile] Попытка обхода ({context})...")

    clicked = False

    for attempt in range(15):
        time.sleep(1)

        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                logging.info(f"  [Turnstile] Найден iframe после {attempt+1}с")

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

                        logging.info(f"  [Turnstile] Целевая точка: ({checkbox_x:.0f}, {checkbox_y:.0f})")

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

                        time.sleep(random.uniform(0.5, 1.0))
                        break

                except Exception as e:
                    logging.warning(f"Ошибка при клике по Turnstile: {e}")

        if clicked:
            break

    if not clicked:
        logging.info(f"  [Turnstile] Iframe не найден за 15с!")
        return False

    logging.info(f"  [Turnstile] Ожидание решения...")
    for i in range(30):
        time.sleep(1)

        if not check_for_turnstile(page):
            logging.info(f"  [Turnstile] ✓ Решен за {i+1}с!")
            time.sleep(20)

            final_url = page.url
            logging.info(f"  [Turnstile] Финальный URL: {final_url[:80]}...")

            if 'secure.indeed.com/auth' in final_url:
                logging.error(f"  [Turnstile] ✗ Редирект на авторизацию!")
                return False

            return True

        if i % 5 == 0 and i > 0:
            logging.info(f"  [Turnstile] Ожидание... {i}/30с")

    logging.info(f"  [Turnstile] ✗ Timeout (30с)")
    return False


# ================== ПАРСИНГ ==================

def extract_emails(page):
    """Извлечение email"""
    emails = set()

    try:
        for link in page.query_selector_all("a[href^='mailto:']"):
            href = link.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0].strip()
            if EMAIL_PATTERN.match(email):
                emails.add(email.lower())

        try:
            body = page.query_selector("body")
            if body:
                visible_text = body.inner_text()
                for email in EMAIL_PATTERN.findall(visible_text):
                    if not any(x in email.lower() for x in ['.png', '.jpg', '.css', '.js', '.svg', '.gif', 'example.com', 'domain.com', 'test.com', 'sentry.io']):
                        emails.add(email.lower())
        except Exception as e:
            logging.warning(f"      Error extracting emails from body text: {e}")

        meta_tags = page.query_selector_all("meta[name*='contact'], meta[property*='contact'], meta[name*='email'], meta[property*='email']")
        for meta in meta_tags:
            content = meta.get_attribute("content") or ""
            for email in EMAIL_PATTERN.findall(content):
                if EMAIL_PATTERN.match(email):
                    emails.add(email.lower())

        json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                content = script.inner_text()
                for email in EMAIL_PATTERN.findall(content):
                    if EMAIL_PATTERN.match(email):
                        emails.add(email.lower())
            except:
                pass

        footer = page.query_selector("footer")
        if footer:
            footer_text = footer.inner_text()
            for email in EMAIL_PATTERN.findall(footer_text):
                if EMAIL_PATTERN.match(email) and not any(x in email.lower() for x in ['.png', '.jpg', '.css', '.js']):
                    emails.add(email.lower())

    except Exception as e:
        logging.warning(f"      Error extracting emails: {e}")

    return list(emails)


def extract_phones(page):
    """Извлечение телефонов с валидацией"""
    phones = set()

    try:
        for link in page.query_selector_all("a[href^='tel:']"):
            href = link.get_attribute("href") or ""
            phone = href.replace("tel:", "").strip()
            normalized = normalize_peru_phone(phone)
            if normalized:
                phones.add(normalized)

        try:
            body = page.query_selector("body")
            if body:
                visible_text = body.inner_text()
                for phone in PHONE_PATTERN.findall(visible_text):
                    normalized = normalize_peru_phone(phone)
                    if normalized:
                        phones.add(normalized)
        except Exception as e:
            logging.warning(f"      Error extracting phones from body text: {e}")

        meta_tags = page.query_selector_all("meta[name*='phone'], meta[property*='phone'], meta[name*='telephone'], meta[property*='telephone']")
        for meta in meta_tags:
            content = meta.get_attribute("content") or ""
            for phone in PHONE_PATTERN.findall(content):
                normalized = normalize_peru_phone(phone)
                if normalized:
                    phones.add(normalized)

        json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                content = script.inner_text()
                for phone in PHONE_PATTERN.findall(content):
                    normalized = normalize_peru_phone(phone)
                    if normalized:
                        phones.add(normalized)
            except:
                pass

        footer = page.query_selector("footer")
        if footer:
            footer_text = footer.inner_text()
            for phone in PHONE_PATTERN.findall(footer_text):
                normalized = normalize_peru_phone(phone)
                if normalized:
                    phones.add(normalized)

    except Exception as e:
        logging.warning(f"      Error extracting phones: {e}")

    return list(phones)


def get_company_indeed_url(page):
    """Получить ссылку на страницу компании на Indeed"""
    company_link = page.query_selector('div[data-testid="inlineHeader-companyName"] a')
    if company_link:
        href = company_link.get_attribute("href")
        if href:
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return f"https://{INDEED_DOMAIN}" + href
    return None


def get_company_website_from_indeed(page, company_indeed_url):
    """Получить сайт компании со страницы компании на Indeed"""
    if not company_indeed_url:
        return None

    logging.info(f"    [Indeed] Страница компании: {company_indeed_url[:70]}...")

    try:
        page.goto(company_indeed_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        if check_for_turnstile(page):
            logging.info(f"    [Turnstile] На странице компании")
            if not bypass_turnstile(page, "company_indeed"):
                return None
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(1)

        website_elem = page.query_selector('li[data-testid="companyInfo-companyWebsite"] a')
        if website_elem:
            url = website_elem.get_attribute("href")
            if url and url.startswith("http") and 'indeed.com' not in url:
                logging.info(f"    [Indeed] Сайт: {url[:70]}...")
                return url

        logging.info(f"    [Indeed] Сайт не найден")
        return None

    except Exception as e:
        logging.error(f"Ошибка получения сайта: {e}")
        return None


def parse_company_website(page, website_url, company_name):
    """Парсинг сайта компании"""
    logging.info(f"    [Web] Парсинг: {website_url[:60]}...")

    all_emails = set()
    all_phones = set()

    try:
        try:
            page.goto(website_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            error_str = str(e)
            if any(err in error_str for err in ["SSL", "SEC_ERROR", "CERT", "REDIRECT_LOOP"]):
                logging.warning(f"Connection error ignored for {website_url}: {type(e).__name__}")
                return {"emails": [], "phones": []}
            raise
        time.sleep(2)

        if check_for_turnstile(page):
            if not bypass_turnstile(page, f"site_{company_name[:20]}"):
                return {"emails": [], "phones": []}
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(1)

        logging.info(f"    [Web] Парсинг главной страницы...")
        emails = extract_emails(page)
        phones = extract_phones(page)
        all_emails.update(emails)
        all_phones.update(phones)
        logging.info(f"    [Web] Главная: {len(emails)} emails, {len(phones)} телефонов")

        contact_keywords = [
            'contact', 'contacto', 'contacta', 'contactar', 'contactanos', 'contactenos',
            'about', 'acerca', 'sobre', 'nosotros', 'quienes-somos',
            'team', 'equipo', 'trabajadores',
            'legal', 'aviso-legal', 'avisolegal', 'terminos',
            'info', 'informacion',
            'ayuda', 'help', 'soporte', 'support',
            'empleo', 'trabajo', 'careers', 'jobs',
            'ubicacion', 'location', 'direccion',
            'impressum', 'imprint', 'privacy', 'privacidad',
            'terms', 'conditions', 'condiciones',
            'footer', 'pie', 'bottom'
        ]
        contact_urls = []

        for link in page.query_selector_all("a[href]")[:300]:
            href = link.get_attribute("href") or ""
            full_url = urljoin(website_url, href)

            if any(kw in full_url.lower() for kw in contact_keywords):
                if full_url not in contact_urls and website_url in full_url:
                    contact_urls.append(full_url)

        logging.info(f"    [Web] Найдено {len(contact_urls)} контактных страниц, проверю до 10")

        for idx, url in enumerate(contact_urls[:10], 1):
            if len(all_emails) >= 3 and len(all_phones) >= 3:
                logging.info(f"    [Web] Достигнут лимит (3 emails + 3 телефона)")
                break

            try:
                logging.info(f"    [Web] Контакт {idx}/10: {url[:60]}...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(1)

                if check_for_turnstile(page):
                    if not bypass_turnstile(page, "contact"):
                        continue
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(1)

                emails = extract_emails(page)
                phones = extract_phones(page)
                all_emails.update(emails)
                all_phones.update(phones)
                logging.info(f"    [Web] +{len(emails)} emails, +{len(phones)} телефонов")
            except Exception as e:
                logging.warning(f"Ошибка парсинга контактной страницы {idx}: {e}")

        final_emails = list(all_emails)[:3]
        final_phones = list(all_phones)[:3]
        logging.info(f"    [Web] ИТОГО: {len(final_emails)} emails, {len(final_phones)} телефонов")

        return {"emails": final_emails, "phones": final_phones}

    except Exception as e:
        logging.error(f"Ошибка парсинга сайта {website_url}: {e}")
        return {"emails": [], "phones": []}


def parse_vacancy(page, vacancy_url, vacancy_title):
    """Парсинг вакансии"""
    result = {
        'Компания': '',
        'Телефон': '',
        'Сайт': '',
        'Email': '',
        'Ссылка на вакансию': vacancy_url,
        'Страна': 'PE'
    }

    try:
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            company_link = company_elem.query_selector("a")
            if company_link:
                result['Компания'] = company_link.inner_text().strip()
            else:
                result['Компания'] = company_elem.inner_text().strip()
        else:
            alt_elem = page.query_selector("[data-company-name='true']")
            if alt_elem:
                result['Компания'] = alt_elem.inner_text().strip()
            else:
                result['Компания'] = "Unknown"

        company_indeed_url = get_company_indeed_url(page)
        if not company_indeed_url:
            logging.info(f"  [!] Ссылка на компанию Indeed не найдена")
            return result

        website = get_company_website_from_indeed(page, company_indeed_url)
        if not website:
            logging.info(f"  [!] Сайт компании не найден на Indeed")
            return result

        result['Сайт'] = website

        contacts = parse_company_website(page, website, result['Компания'])

        emails = contacts.get('emails', [])
        phones = contacts.get('phones', [])

        result['Email'] = "; ".join(emails) if emails else ''
        result['Телефон'] = "; ".join(phones) if phones else ''

        logging.info(f"  ИТОГО: {len(emails)} emails, {len(phones)} телефонов")

    except Exception as e:
        logging.error(f"Ошибка парсинга вакансии {vacancy_url}: {e}")

    return result


def get_company_name_from_vacancy(page, vacancy_url):
    """Извлечение названия компании"""
    try:
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        if check_for_turnstile(page):
            if not bypass_turnstile(page, "vacancy"):
                return None

        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            company_link = company_elem.query_selector("a")
            if company_link:
                return company_link.inner_text().strip()
            return company_elem.inner_text().strip()

        alt_elem = page.query_selector("[data-company-name='true']")
        if alt_elem:
            return alt_elem.inner_text().strip()

        return "Unknown"

    except Exception as e:
        logging.error(f"Ошибка извлечения компании: {e}")
        return None


# ================== ПАРСИНГ ОДНОЙ СТРАНИЦЫ ==================

def parse_single_page(browser, page_num, seen_companies, search_query):
    """Парсит одну страницу поиска Indeed"""
    page_data = []
    had_challenge = False
    turnstile_count = 0

    page = browser.new_page()
    page.set_default_timeout(30000)

    try:
        base_url = f"https://{INDEED_DOMAIN}/jobs?q={search_query}&l="
        if page_num == 1:
            url = base_url
        else:
            url = base_url + f"&start={(page_num-1)*10}"

        logging.info(f"Loading: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        logging.info(f"[DEBUG] Page loaded, current URL: {page.url}")
        logging.info(f"[DEBUG] Page title: {page.title()}")

        try:
            jobs_count = page.locator("a.jcs-JobTitle").count()
            logging.info(f"[DEBUG] Found {jobs_count} job title elements on page")
        except Exception as e:
            logging.error(f"[DEBUG] Error counting job titles: {e}")

        try:
            timestamp = int(time.time())
            html_file = results_dir / f"debug_page{page_num}_{timestamp}.html"
            screenshot_file = results_dir / f"debug_page{page_num}_{timestamp}.png"

            html_content = page.content()
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info(f"[DEBUG] Saved HTML to {html_file}")

            page.screenshot(path=str(screenshot_file), full_page=False)
            logging.info(f"[DEBUG] Saved screenshot to {screenshot_file}")
        except Exception as e:
            logging.error(f"[DEBUG] Error saving debug files: {e}")

        current_url = page.url
        page_title = page.title()

        if '__cf_chl_rt_tk=' in current_url or 'Control de seguridad' in page_title or 'Un momento' in page_title:
            had_challenge = True
            logging.info(f"[Cloudflare] Обнаружен Cloudflare Challenge! Title: {page_title}")

            logging.info("[Cloudflare] Попытка пройти Turnstile чекбокс...")
            if bypass_turnstile(page, f"cloudflare_challenge_page{page_num}"):
                logging.info("[Cloudflare] ✓ Turnstile пройден!")
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(2)
            else:
                logging.warning("[Cloudflare] Turnstile не удалось пройти, ждем автоматического разрешения...")
                max_wait = 30
                for i in range(max_wait):
                    time.sleep(1)
                    current_url = page.url
                    page_title = page.title()

                    if '__cf_chl_rt_tk=' not in current_url and 'Control de seguridad' not in page_title and 'Un momento' not in page_title:
                        logging.info(f"[Cloudflare] ✓ Challenge разрешен за {i+1}с!")
                        break
                else:
                    logging.warning(f"[Cloudflare] Challenge не разрешился за {max_wait}с, перезагрузка...")
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=60000)
                        time.sleep(3)

                        current_url = page.url
                        page_title = page.title()

                        if '__cf_chl_rt_tk=' in current_url or 'Control de seguridad' in page_title:
                            logging.error("[Cloudflare] ✗ Challenge не разрешился")
                            return [], had_challenge
                    except Exception as e:
                        logging.error(f"[Cloudflare] Ошибка при перезагрузке: {e}")
                        return [], had_challenge

                time.sleep(2)

        max_turnstile_attempts = 5
        for attempt in range(max_turnstile_attempts):
            if check_for_turnstile(page):
                had_challenge = True
                turnstile_count += 1

                logging.info(f"[Turnstile #{turnstile_count}] Обнаружен на странице поиска!")

                if not bypass_turnstile(page, f"search_page_{page_num}_attempt{turnstile_count}"):
                    logging.info(f"[Turnstile #{turnstile_count}] ✗ Не удалось решить!")
                    return [], had_challenge

                logging.info(f"[Turnstile #{turnstile_count}] Ожидание загрузки...")
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                time.sleep(15)
            else:
                break

        if turnstile_count >= 3:
            logging.info(f"[MANUAL REDIRECT] Решено {turnstile_count} Turnstile!")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(10)
            except Exception as e:
                logging.error(f"[MANUAL REDIRECT] ✗ Ошибка: {e}")
                return [], had_challenge

        current_url = page.url
        if 'secure.indeed.com/auth' in current_url:
            logging.error(f"[ERROR] Редирект на авторизацию: {current_url[:80]}...")

            if relogin_with_cookies(page, url):
                logging.info(f"[Auth] ✓ Повторный логин успешен")
                current_url = page.url
                if 'secure.indeed.com/auth' in current_url:
                    return [], had_challenge
            else:
                return [], had_challenge

        try:
            debug_path = results_dir / f"debug_page{page_num}.png"
            page.screenshot(path=str(debug_path))

            html_path = results_dir / f"debug_page{page_num}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
        except Exception as e:
            logging.info(f"[DEBUG] Ошибка сохранения: {e}")

        logging.info("[WAITING] Ожидание появления вакансий (таймаут 60с)...")
        page.wait_for_selector("a.jcs-JobTitle", timeout=60000)

        vacancy_links = []
        for link_elem in page.query_selector_all("a.jcs-JobTitle"):
            title = link_elem.inner_text().strip()
            href = link_elem.get_attribute("href")
            if href:
                full_url = f"https://{INDEED_DOMAIN}" + href if href.startswith("/") else href
                vacancy_links.append({'title': title, 'url': full_url})

        logging.info(f"\nFound {len(vacancy_links)} vacancies\n")

        for idx, vac in enumerate(vacancy_links, 1):
            logging.info(f"\n[{idx}/{len(vacancy_links)}] {'-'*60}")
            logging.info(f"  Вакансия: {vac['title'][:60]}...")
            logging.info(f"  URL: {vac['url'][:80]}...")

            company_name = get_company_name_from_vacancy(page, vac['url'])
            if not company_name:
                logging.warning(f"  [!] Не удалось извлечь компанию")
                continue

            logging.info(f"  Компания: {company_name}")

            company_key = company_name.lower().strip()
            if company_key in seen_companies:
                logging.info(f"  [SKIP] Компания уже обработана!")
                continue

            data = parse_vacancy(page, vac['url'], vac['title'])
            seen_companies.add(company_key)
            page_data.append(data)

            time.sleep(2)

    except Exception as e:
        logging.error(f"Error parsing page {page_num}: {e}")

    finally:
        page.close()

    return page_data, had_challenge


# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

class BrowserContext:
    """Контекст для управления браузером"""
    def __init__(self, proxy_config=None):
        self.proxy_config = proxy_config
        self.camoufox_params = {
            'headless': False if platform.system() == "Linux" else HEADLESS_MODE,
            'humanize': True,
            'os': 'windows',
            'locale': 'es-PE',  # Перуанська локаль
            'geoip': False,
            'addons': [],
        }

        if proxy_config:
            self.camoufox_params['proxy'] = proxy_config

        self._camoufox = None
        self._browser = None

    def __enter__(self):
        self._camoufox = Camoufox(**self.camoufox_params)
        self._browser = self._camoufox.__enter__()
        self._inject_stealth_scripts()
        return self._browser

    def _inject_stealth_scripts(self):
        """Внедряем JavaScript для подмены fingerprint"""
        if not self._browser:
            return

        stealth_js = """
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 6,
            configurable: true
        });

        const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {
            return 300; // UTC-5 (Peru)
        };

        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(contextType, ...args) {
            if (contextType === 'webgl' || contextType === 'webgl2' || contextType === 'experimental-webgl') {
                const gl = originalGetContext.call(this, contextType, ...args);
                if (gl) {
                    const originalGetParameter = gl.getParameter.bind(gl);
                    gl.getParameter = function(parameter) {
                        if (parameter === 37445) {
                            return 'Google Inc. (NVIDIA)';
                        }
                        if (parameter === 37446) {
                            return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)';
                        }
                        return originalGetParameter(parameter);
                    };
                }
                return gl;
            }
            return originalGetContext.call(this, contextType, ...args);
        };

        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }

        console.log('[STEALTH] Fingerprint injections applied for Peru');
        """

        webrtc_block_script = """
        (() => {
            if (window.hasRunWebRTCBlock) return;
            window.hasRunWebRTCBlock = true;

            const OriginalRTCPeerConnection = window.RTCPeerConnection ||
                                              window.mozRTCPeerConnection ||
                                              window.webkitRTCPeerConnection;

            if (!OriginalRTCPeerConnection) return;

            function RTCPeerConnectionModified(config, constraints) {
                if (config && config.iceServers) {
                    config.iceServers = [];
                }
                return new OriginalRTCPeerConnection(config, constraints);
            }

            RTCPeerConnectionModified.prototype = OriginalRTCPeerConnection.prototype;
            window.RTCPeerConnection = RTCPeerConnectionModified;
            window.mozRTCPeerConnection = RTCPeerConnectionModified;
            window.webkitRTCPeerConnection = RTCPeerConnectionModified;

            console.log('[WEBRTC BLOCK] Enabled');
        })();
        """

        if self._browser.contexts:
            context = self._browser.contexts[0]
        else:
            context = self._browser.new_context()

        context.add_init_script(stealth_js)
        context.add_init_script(webrtc_block_script)
        logging.info("[STEALTH] Fingerprint injections enabled for Peru (TZ=UTC-5)")

    def __exit__(self, *args):
        if self._camoufox:
            self._camoufox.__exit__(*args)

    def close(self):
        if self._camoufox:
            self._camoufox.__exit__(None, None, None)
            self._camoufox = None
            self._browser = None


def create_browser_with_proxy(proxy_config=None):
    return BrowserContext(proxy_config)


def close_browser_safely(browser):
    if browser is None:
        return
    if hasattr(browser, '_browser_context'):
        browser._browser_context.close()
    else:
        try:
            browser.close()
        except Exception as e:
            logging.warning(f"Error closing browser: {e}")


def relogin_with_cookies(page, target_url):
    """Повторная авторизация через cookies"""
    try:
        logging.warning(f"[Auth] Требуется авторизация, попытка автологина через cookies...")

        cookies_file = "indeed_cookies.json"
        try:
            cookies = load_cookies_from_json(cookies_file)
            logging.info(f"[Auth] Загружено {len(cookies)} cookies")
        except Exception as e:
            logging.error(f"[Auth] Не удалось загрузить cookies: {e}")
            return False

        context = page.context
        try:
            apply_cookies_to_context(context, cookies)
            logging.info(f"[Auth] Cookies применены")
        except Exception as e:
            logging.error(f"[Auth] Не удалось применить cookies: {e}")
            return False

        logging.info(f"[Auth] Переход на: {target_url[:80]}...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        current_url = page.url
        if 'secure.indeed.com/auth' in current_url:
            logging.error(f"[Auth] ✗ Cookies не помогли")
            return False

        logging.info(f"[Auth] ✓ Успешно!")
        return True

    except Exception as e:
        logging.error(f"[Auth] Ошибка: {e}")
        return False


def warmup_browser(browser):
    """Прогрев браузера"""
    try:
        logging.info("  [Прогрев] google.com.pe...")
        page = browser.new_page()
        page.goto("https://www.google.com.pe", wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(2, 4))
        page.close()

        logging.info("  [Прогрев] wikipedia.org...")
        page = browser.new_page()
        page.goto("https://www.wikipedia.org", wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(2, 4))
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(random.uniform(1, 2))
        page.close()

        logging.info("  [Прогрев] Готово!\n")
    except Exception as e:
        logging.warning(f"Browser warmup failed: {e}")


# ================== MAIN ==================

def main():
    logging.info("\n" + "="*80)
    logging.info("Indeed Parser v5.0 - PERU (pe.indeed.com)")
    logging.info(f"Search queries: {', '.join(SEARCH_QUERIES)}")
    logging.info(f"Pages per query: {PAGES_PER_QUERY}")
    logging.info(f"Results: {results_dir}")
    logging.info("="*80 + "\n")

    payload = {
        "message": "Скрипт indeed.pe активирован!",
        "time": datetime.now(kiev_tz).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "indeed.pe"
    }
    send_webhook(WEBHOOK_START_URL, payload)

    all_data = []
    seen_companies = set()

    current_browser = None
    first_browser = True

    # Ітерація по всіх пошукових запитах
    total_pages = 0
    for query_idx, search_query in enumerate(SEARCH_QUERIES):
        logging.info(f"\n{'#'*80}")
        logging.info(f"SEARCH QUERY {query_idx+1}/{len(SEARCH_QUERIES)}: {search_query}")
        logging.info(f"{'#'*80}\n")

        for page_num in range(1, PAGES_PER_QUERY + 1):
            total_pages += 1
            logging.info(f"\n{'='*80}")
            logging.info(f"[{search_query}] PAGE {page_num}/{PAGES_PER_QUERY} (Total: {total_pages})")
            logging.info(f"{'='*80}\n")

            if current_browser is None:
                if USE_PROXIES:
                    proxy_config = {
                        'server': 'p.webshare.io:80',
                        'username': 'dbgrpsyu-PE-rotate',
                        'password': 'YOUR_PASSWORD'
                    }
                    logging.info(f"[Proxy] Using ROTATING endpoint: {proxy_config['server']}")
                    browser_context = create_browser_with_proxy(proxy_config)
                else:
                    browser_context = create_browser_with_proxy(None)

                current_browser = browser_context.__enter__()
                current_browser._browser_context = browser_context

                if first_browser:
                    warmup_browser(current_browser)
                    first_browser = False

                    logging.info("\n Starting detailed network logging...")
                    network_logger = NetworkLogger()

                    test_page = current_browser.new_page()
                    try:
                        test_page.goto("https://www.google.com.pe", wait_until="domcontentloaded", timeout=60000)
                        time.sleep(2)

                        proxy_config = None
                        if USE_PROXIES:
                            proxy_config = {
                                'server': 'p.webshare.io:80',
                                'username': 'dbgrpsyu-PE-rotate',
                                'password': 'YOUR_PASSWORD'
                            }

                        network_logger.log_full_network_state(
                            page=test_page,
                            proxy_config=proxy_config,
                            url="https://www.google.com.pe"
                        )

                    except Exception as e:
                        logging.error(f"Ошибка детального логирования: {e}")
                    finally:
                        test_page.close()

                    logging.info("Detailed network logging completed\n")

            page_data, had_challenge = parse_single_page(current_browser, page_num, seen_companies, search_query)
            all_data.extend(page_data)

    if current_browser:
        close_browser_safely(current_browser)

    logging.info(f"\n{'='*80}")
    logging.info("SAVING RESULTS")
    logging.info(f"{'='*80}\n")

    seen_companies_dict = {}
    deduped_data = []
    for item in all_data:
        company_name = item['Компания'].lower().strip()
        if company_name not in seen_companies_dict:
            seen_companies_dict[company_name] = item
            deduped_data.append(item)
        else:
            existing = seen_companies_dict[company_name]
            existing_emails = set(existing['Email'].split("; ")) if existing['Email'] else set()
            new_emails = set(item['Email'].split("; ")) if item['Email'] else set()
            existing['Email'] = "; ".join(sorted(existing_emails | new_emails))

    duplicates_removed = len(all_data) - len(deduped_data)
    if duplicates_removed > 0:
        logging.info(f"\nУдалено дубликатов компаний: {duplicates_removed}")
    all_data = deduped_data

    if not all_data:
        logging.info("\n Нет данных для сохранения!")
        return

    df = pd.DataFrame(all_data)
    cols = ['Компания', 'Телефон', 'Сайт', 'Email', 'Ссылка на вакансию', 'Страна']
    df = df[cols]

    excel_file = results_dir / f"indeed_results_{current_time}.xlsx"
    df.to_excel(excel_file, index=False, engine='openpyxl')
    logging.info(f"Saved Excel: {excel_file.name}")

    wb = load_workbook(excel_file)
    ws = wb.active
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        adjusted_width = length + 2
        ws.column_dimensions[column_cells[0].column_letter].width = adjusted_width
    wb.save(excel_file)

    total = len(all_data)
    with_emails = len([d for d in all_data if d['Email']])
    with_phones = len([d for d in all_data if d['Телефон']])
    with_websites = len([d for d in all_data if d['Сайт']])
    total_emails = sum(len(d['Email'].split("; ")) for d in all_data if d['Email'])
    total_phones = sum(len(d['Телефон'].split("; ")) for d in all_data if d['Телефон'])

    logging.info(f"Total vacancies:   {total}")
    logging.info(f"With websites:     {with_websites} ({with_websites/total*100:.1f}%)" if total > 0 else "")
    logging.info(f"With emails:       {with_emails} ({with_emails/total*100:.1f}%)" if total > 0 else "")
    logging.info(f"With phones:       {with_phones} ({with_phones/total*100:.1f}%)" if total > 0 else "")
    logging.info(f"Total emails:      {total_emails}")
    logging.info(f"Total phones:      {total_phones}")
    logging.info(f"\nSaved: {excel_file.name}")

    logging.info(f"\n{'='*80}")
    logging.info("ОТПРАВКА НА WEBHOOK")
    logging.info(f"{'='*80}\n")

    webhook_payload = {
        "source": "indeed.pe",
        "data": all_data
    }

    if send_webhook(WEBHOOK_RESULTS_URL, webhook_payload, timeout=30):
        logging.info(f"Всего компаний отправлено: {len(all_data)}")
    else:
        logging.info(f"Ошибка отправки на webhook")

    logging.info(f"\n{'='*80}\n")
    logging.info(f"Done: {total} vacancies, {with_websites} websites, {total_emails} emails, {total_phones} phones")

if __name__ == "__main__":
    main()
