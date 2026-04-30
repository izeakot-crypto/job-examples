#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indeed Parser v5.0 - Argentina (ar.indeed.com)

Парсер для аргентинского Indeed по запросу "Call Center"

Простая логика:
1. Собираем ссылки на вакансии с Indeed Argentina
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

INDEED_SEARCH_URL = "https://ar.indeed.com/jobs?q=Call+Center&l="
PAGES_TO_PARSE = 10  # Парсинг 10 страниц для Аргентины
HEADLESS_MODE = True  # True - headless режим, False - видимый браузер
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# ================== НАСТРОЙКА ПРОКСИ ==================

USE_PROXIES = False  # Отключено: работаем напрямую через украинский IP
PROXY_CONFIG_FILE = "webshare_config.json"  # Файл конфигурации Webshare

# Инициализация менеджера прокси (если включены)
proxy_manager = None
proxy_config = None

# Прокси включены - новый Webshare аккаунт + WebRTC защита
if USE_PROXIES:
    try:
        # Загружаем конфигурацию
        ws_config = load_webshare_config(PROXY_CONFIG_FILE)

        # Инициализируем менеджер прокси
        proxy_manager = WebshareProxyManager(
            api_key=ws_config['api_key'],
            mode=ws_config.get('mode', 'direct'),
            country_codes=ws_config.get('country_codes', []),
            check_health=ws_config.get('check_health', False),
            health_timeout=ws_config.get('health_timeout', 10),
            preferred_protocol=ws_config.get('preferred_protocol', 'http')
        )

        # Инициализируем менеджер ротации (БУДЕТ СОЗДАН В main(), здесь только заглушка)
        # proxy_rotation_manager будет создан в main() после полного запуска

        if proxy_manager.get_proxy_count() > 0:
            logging.info(f"🔐 Прокси включён: всего {proxy_manager.get_proxy_count()} прокси")
            logging.info(f"  [Proxy] Всего доступно: {proxy_manager.get_proxy_count()} прокси")
        else:
            logging.warning("⚠️  Не удалось загрузить прокси, работаем без прокси")
            USE_PROXIES = False
            proxy_manager = None

    except FileNotFoundError:
        logging.warning(f"⚠️  Файл конфигурации прокси не найден: {PROXY_CONFIG_FILE}")
        logging.info(f"  [Proxy] Работаем без прокси (создайте {PROXY_CONFIG_FILE} для использования прокси)")
        USE_PROXIES = False
        proxy_manager = None
    except Exception as e:
        logging.error(f"❌ Ошибка инициализации прокси: {e}")
        logging.info(f"  [Proxy] Ошибка: {e}, работаем без прокси")
        USE_PROXIES = False
        proxy_manager = None

# Регулярки
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
# Испанские телефоны: +34 или 34 или без префикса, начинаются с 6-9
PHONE_PATTERN = re.compile(r'(?:\+34|0034|34)?[\s.-]?[6-9]\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}')


def normalize_spanish_phone(phone_str):
    """
    Нормализация и валидация испанского телефона

    Правила:
    - Мобильные: начинаются с 6 или 7 (например: 600 000 000 - 799 999 999)
    - Стационарные: начинаются с 8 или 9 (например: 800 000 000 - 999 999 999)
    - Формат: 9 цифр после кода страны (+34)
    - Исключаем: повторяющиеся цифры (111111111), последовательности (123456789)

    Возвращает: нормализованный телефон в формате +34XXXXXXXXX или None если невалиден
    """
    if not phone_str:
        return None

    # Очистка от всех символов кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone_str)

    # Убираем код страны если есть
    if cleaned.startswith('+34'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0034'):
        cleaned = cleaned[4:]
    elif cleaned.startswith('34') and len(cleaned) > 9:
        cleaned = cleaned[2:]

    # Должно остаться ровно 9 цифр
    if len(cleaned) != 9:
        return None

    # Первая цифра должна быть 6, 7, 8 или 9
    if cleaned[0] not in ['6', '7', '8', '9']:
        return None

    # Исключаем одинаковые цифры (111111111, 222222222, etc)
    if len(set(cleaned)) == 1:
        logging.debug(f"      Phone rejected (all same digits): {phone_str}")
        return None

    # Исключаем простые последовательности
    if cleaned in ['123456789', '987654321', '012345678', '876543210']:
        logging.debug(f"      Phone rejected (sequence): {phone_str}")
        return None

    # Исключаем телефоны с более чем 4 повторяющимися цифрами подряд
    for i in range(len(cleaned) - 3):
        if len(set(cleaned[i:i+4])) == 1:
            logging.debug(f"      Phone rejected (4+ repeating digits): {phone_str}")
            return None

    # Исключаем номера с недостаточным разнообразием цифр (минимум 4 уникальных)
    if len(set(cleaned)) < 4:
        logging.debug(f"      Phone rejected (less than 4 unique digits): {phone_str}")
        return None

    # Дополнительная проверка: исключаем явно подозрительные паттерны
    # Исключаем номера где первые 3 цифры = последним 3 (817667817, 689000689)
    if cleaned[:3] == cleaned[-3:]:
        logging.debug(f"      Phone rejected (first 3 = last 3): {phone_str}")
        return None

    # Исключаем номера с подозрительными паттернами (8XX, 7XX, которые не похожи на реальные)
    # Стационарные обычно начинаются с 9XX (Мадрид, Барселона, и т.д.)
    # Мобильные с 6XX, 7XX - но 7XX редкие
    if cleaned[0] == '7' and int(cleaned[1]) > 7:
        # 78X, 79X очень редкие диапазоны
        logging.debug(f"      Phone rejected (rare 7XX range): {phone_str}")
        return None

    if cleaned[0] == '8':
        # 8XX - это обычно бесплатные номера, не контактные
        # Реальные номера обычно 9XX
        # Оставим только если это явно выглядит как реальный
        pass  # Пока разрешаем

    # Возвращаем нормализованный формат: +34XXXXXXXXX (БЕЗ пробелов)
    return f"+34{cleaned}"

# Результаты
kiev_tz = pytz.timezone('Europe/Kiev')
current_time = datetime.now(kiev_tz).strftime("%Y-%m-%d_%H-%M-%S")
results_dir = Path(f"results_{current_time}")
results_dir.mkdir(exist_ok=True)

# Логирование
log_file = results_dir / f"parser_log_{current_time}.txt"

# Очищаем все существующие handlers (чтобы избежать дублирования)
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# Настраиваем логирование заново
logging.basicConfig(
    level=logging.DEBUG,  # Максимально детальное логирование
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ],
    force=True  # Форсируем переконфигурацию
)

# Устанавливаем уровень DEBUG для всех логгеров
logging.getLogger().setLevel(logging.DEBUG)

logging.info("="*80)
logging.info(f"Лог файл создан: {log_file}")
logging.info("="*80)


# ================== УПРАВЛЕНИЕ РОТАЦИЕЙ ПРОКСИ ==================

# ПРОКСИ ОТКЛЮЧЕНЫ - класс ProxyRotationManager закомментирован
# class ProxyRotationManager:
#     """
#     Менеджер ротации прокси с умной логикой
#
#     Стратегии:
#     1. Ротация каждые N страниц
#     2. Ротация при множественных Cloudflare challenge (> 3 раз подряд)
#     """
#
#     def __init__(self, proxy_manager, rotation_interval=3, max_challenges=3):
#         """
#         Args:
#             proxy_manager: Экземпляр WebshareProxyManager
#             rotation_interval: Менять прокси каждые N страниц (по умолчанию 3)
#             max_challenges: Максимальное количество challenge подряд до смены прокси
#         """
#         self.proxy_manager = proxy_manager
#         self.rotation_interval = rotation_interval
#         self.max_challenges = max_challenges
#
#         # Состояние
#         self.current_proxy = None
#         self.page_count = 0  # Счётчик обработанных страниц
#         self.challenge_count = 0  # Счётчик подряд идущих challenge
#         self.total_rotations = 0  # Общее количество ротаций
#
#         logging.info(f"ProxyRotationManager initialized: interval={rotation_interval}, max_challenges={max_challenges}")
#
#     def get_current_proxy(self):
#         """Получить текущий прокси (или выбрать новый если первый запуск)"""
#         if self.current_proxy is None:
#             self.current_proxy = self.proxy_manager.get_random_proxy()
#             logging.info(f"[Proxy] Initial proxy selected: {self.current_proxy['server']}")
#         return self.current_proxy
#
#     def should_rotate(self, had_challenge=False):
#         """
#         Проверить, нужно ли сменить прокси
#
#         Args:
#             had_challenge: Бы ли на этой странице Cloudflare challenge
#
#         Returns:
#             True если нужно сменить прокси, False иначе
#         """
#         self.page_count += 1
#
#         reason = None
#
#         # Стратегия 1: Ротация по счётчику страниц
#         if self.page_count % self.rotation_interval == 0:
#             reason = f"page_count (every {self.rotation_interval} pages)"
#
#         # Стратегия 2: Ротация при множественных challenge
#         if had_challenge:
#             self.challenge_count += 1
#             logging.warning(f"[Proxy] Cloudflare challenge detected! Count: {self.challenge_count}/{self.max_challenges}")
#
#             if self.challenge_count >= self.max_challenges:
#                 reason = f"too many challenges ({self.challenge_count} in a row)"
#         else:
#             # Сбрасываем счётчик challenge если страница прошла успешно
#             if self.challenge_count > 0:
#                 logging.info(f"[Proxy] Challenge streak broken! Resetting count from {self.challenge_count} to 0")
#             self.challenge_count = 0
#
#         if reason:
#             logging.warning(f"[Proxy] Rotation needed: {reason}")
#             return True
#
#         return False
#
#     def rotate_proxy(self):
#         """Сменить прокси на новый"""
#         if self.current_proxy:
#             # Помечаем старый прокси как нерабочий (если было много challenge)
#             if self.challenge_count >= self.max_challenges:
#                 logging.warning(f"[Proxy] Marking current proxy as failed due to challenges")
#                 self.proxy_manager.mark_proxy_failed(self.current_proxy)
#
#         old_proxy = self.current_proxy
#         self.current_proxy = self.proxy_manager.get_next_proxy()
#         self.total_rotations += 1
#
#         logging.info(f"[Proxy] Rotated: {old_proxy['server'] if old_proxy else 'None'} -> {self.current_proxy['server']}")
#         logging.info(f"[Proxy] Total rotations: {self.total_rotations}, Pages processed: {self.page_count}")
#
#         # Сбрасываем счётчик challenge после смены прокси
#         self.challenge_count = 0
#
#         return self.current_proxy
#
#     def get_stats(self):
#         """Получить статистику ротации"""
#         return {
#             'total_rotations': self.total_rotations,
#             'pages_processed': self.page_count,
#             'current_challenges': self.challenge_count,
#             'current_proxy': self.current_proxy['server'] if self.current_proxy else None
#         }


# Глобальный менеджер ротации (инициализируется в main())
proxy_rotation_manager = None


# ================== TURNSTILE BYPASS ==================

def check_for_turnstile(page):
    """Проверка АКТИВНОГО Turnstile (не просто упоминания в HTML!)"""
    try:
        # 1. Ищем видимый виджет
        widget = page.query_selector("div[data-sitekey], div.cf-turnstile, #cf-turnstile-container")
        if widget:
            bbox = widget.bounding_box()
            if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                return True

        # 2. Ищем активный iframe
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                try:
                    elem = frame.frame_element()
                    bbox = elem.bounding_box()
                    if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                        return True
                except:
                    pass

        # 3. Заголовок страницы
        title = (page.title() or "").lower()
        if 'just a moment' in title or 'challenge' in title:
            return True

        # 4. Проверка на "Verificacion" ТОЛЬКО если есть активный iframe
        # (предотвращаем бесконечные ложные срабатывания)
        page_text = page.inner_text("body").lower() if page.query_selector("body") else ""
        if 'verificacion' in page_text or 'verificación' in page_text:
            # Дополнительная проверка: есть ли активный Cloudflare iframe?
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
                logging.info(f"  [DEBUG] Обнаружено 'Verificacion' + активный Cloudflare iframe!")
                # Сохраняем HTML для анализа
                debug_file = results_dir / f"debug_verificacion_{int(time.time())}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                logging.info(f"  [DEBUG] HTML сохранен: {debug_file.name}")
                return True

        return False
    except:
        return False


def bypass_turnstile(page, context=""):
    """
    Обход Cloudflare Turnstile

    Логика:
    1. Ждем до 15 секунд, пока появится iframe
    2. Проверяем каждую секунду все frames
    3. Кликаем по координатам: x = coord_x + width/9, y = coord_y + height/2
    4. Ждем до 20 секунд решения
    """
    logging.info(f"  [Turnstile] Попытка обхода ({context})...")
    logging.info(f"Turnstile bypass: {context}")

    clicked = False

    # Ждем появления iframe (до 15 сек)
    for attempt in range(15):
        time.sleep(1)

        # Проверяем все frames на странице
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

                        # Вычисляем координаты чекбокса с небольшой случайностью
                        checkbox_x = coord_x + width / 9 + random.uniform(-2, 2)
                        checkbox_y = coord_y + height / 2 + random.uniform(-2, 2)

                        logging.info(f"  [Turnstile] Bbox: x={coord_x:.0f}, y={coord_y:.0f}, w={width:.0f}, h={height:.0f}")
                        logging.info(f"  [Turnstile] Целевая точка: ({checkbox_x:.0f}, {checkbox_y:.0f})")
                        logging.info(f"Turnstile click: x={checkbox_x:.1f}, y={checkbox_y:.1f}, context={context}")

                        # Имитация человеческого поведения - случайные движения мыши
                        logging.info(f"  [Turnstile] Движения мыши...")

                        # Начальная позиция - где-то на странице
                        start_x = random.randint(100, 800)
                        start_y = random.randint(100, 400)
                        page.mouse.move(start_x, start_y)
                        time.sleep(random.uniform(0.1, 0.3))

                        # Промежуточная точка (более естественное движение)
                        mid_x = (start_x + checkbox_x) / 2 + random.uniform(-20, 20)
                        mid_y = (start_y + checkbox_y) / 2 + random.uniform(-20, 20)
                        page.mouse.move(mid_x, mid_y)
                        time.sleep(random.uniform(0.15, 0.35))

                        # Наводимся на чекбокс
                        page.mouse.move(checkbox_x, checkbox_y)
                        time.sleep(random.uniform(0.3, 0.6))

                        # Кликаем
                        logging.info(f"  [Turnstile] Клик!")
                        page.mouse.click(checkbox_x, checkbox_y)
                        clicked = True

                        # Небольшая задержка после клика (как человек)
                        time.sleep(random.uniform(0.5, 1.0))
                        break

                except Exception as e:
                    logging.warning(f"Ошибка при клике по Turnstile: {e}")

        if clicked:
            break

    if not clicked:
        logging.info(f"  [Turnstile] Iframe не найден за 15с!")
        return False

    # Ждем решения (до 30 сек)
    logging.info(f"  [Turnstile] Ожидание решения...")
    for i in range(30):
        time.sleep(1)

        if not check_for_turnstile(page):
            logging.info(f"  [Turnstile] ✓ Решен за {i+1}с!")
            logging.info(f"Turnstile solved: {context}, time={i+1}s")

            # Даем странице время на полную загрузку после решения
            # Увеличено время ожидания для более надежной загрузки
            logging.info(f"  [Turnstile] Ожидание полной загрузки страницы...")
            time.sleep(20)  # Увеличено с 5 до 20 секунд для обработки Interactive Challenge

            # Теперь проверяем финальный URL
            final_url = page.url
            logging.info(f"  [Turnstile] Финальный URL: {final_url[:80]}...")
            logging.info(f"Final URL after Turnstile: {final_url}")

            # Если финальный URL - это страница авторизации, пробуем залогиниться
            if 'secure.indeed.com/auth' in final_url:
                logging.info(f"  [Turnstile] ✗ Финальный редирект на авторизацию!")
                logging.error(f"Final redirect to login page: {final_url}")

                # Пытаемся повторно залогиниться
                original_url = page.url.split('?')[0].split('&continue=')[-1] if '&continue=' in page.url else page.url
                if relogin_with_cookies(page, original_url):
                    logging.info(f"  [Turnstile] ✓ Повторный логин успешен после Turnstile")
                    return True
                else:
                    logging.error(f"  [Turnstile] ✗ Повторный логин не удался")
                    return False

            return True

        if i % 5 == 0 and i > 0:
            logging.info(f"  [Turnstile] Ожидание... {i}/30с")

    logging.info(f"  [Turnstile] ✗ Timeout (30с)")
    return False


# ================== ПАРСИНГ ==================

def extract_emails(page):
    """Извлечение email с улучшенным парсингом"""
    emails = set()

    try:
        # 1. mailto: ссылки
        for link in page.query_selector_all("a[href^='mailto:']"):
            href = link.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0].strip()
            if EMAIL_PATTERN.match(email):
                emails.add(email.lower())
                logging.debug(f"      Found email (mailto): {email.lower()}")

        # 2. Видимый текст страницы (НЕ весь HTML!)
        try:
            body = page.query_selector("body")
            if body:
                visible_text = body.inner_text()
                for email in EMAIL_PATTERN.findall(visible_text):
                    if not any(x in email.lower() for x in ['.png', '.jpg', '.css', '.js', '.svg', '.gif', 'example.com', 'domain.com', 'test.com', 'sentry.io']):
                        emails.add(email.lower())
                        logging.debug(f"      Found email (text): {email.lower()}")
        except Exception as e:
            logging.warning(f"      Error extracting emails from body text: {e}")

        # 3. Meta теги
        meta_tags = page.query_selector_all("meta[name*='contact'], meta[property*='contact'], meta[name*='email'], meta[property*='email']")
        for meta in meta_tags:
            content = meta.get_attribute("content") or ""
            for email in EMAIL_PATTERN.findall(content):
                if EMAIL_PATTERN.match(email):
                    emails.add(email.lower())
                    logging.debug(f"      Found email (meta): {email.lower()}")

        # 4. JSON-LD structured data
        json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                content = script.inner_text()
                for email in EMAIL_PATTERN.findall(content):
                    if EMAIL_PATTERN.match(email):
                        emails.add(email.lower())
                        logging.debug(f"      Found email (json-ld): {email.lower()}")
            except:
                pass

        # 5. Футер отдельно (там часто контакты)
        footer = page.query_selector("footer")
        if footer:
            footer_text = footer.inner_text()
            for email in EMAIL_PATTERN.findall(footer_text):
                if EMAIL_PATTERN.match(email) and not any(x in email.lower() for x in ['.png', '.jpg', '.css', '.js']):
                    emails.add(email.lower())
                    logging.debug(f"      Found email (footer): {email.lower()}")

    except Exception as e:
        logging.warning(f"      Error extracting emails: {e}")

    return list(emails)


def extract_phones(page):
    """Извлечение телефонов с валидацией и нормализацией (БЕЗ пробелов)"""
    phones = set()

    try:
        # 1. tel: ссылки
        for link in page.query_selector_all("a[href^='tel:']"):
            href = link.get_attribute("href") or ""
            phone = href.replace("tel:", "").strip()
            normalized = normalize_spanish_phone(phone)
            if normalized:
                phones.add(normalized)
                logging.debug(f"      Found valid phone (tel): {normalized}")

        # 2. Видимый текст страницы (НЕ весь HTML!)
        # Используем inner_text вместо content() чтобы избежать мусора из JS/CSS/атрибутов
        try:
            body = page.query_selector("body")
            if body:
                visible_text = body.inner_text()
                for phone in PHONE_PATTERN.findall(visible_text):
                    normalized = normalize_spanish_phone(phone)
                    if normalized:
                        phones.add(normalized)
                        logging.debug(f"      Found valid phone (text): {normalized}")
        except Exception as e:
            logging.warning(f"      Error extracting phones from body text: {e}")

        # 3. Meta теги
        meta_tags = page.query_selector_all("meta[name*='phone'], meta[property*='phone'], meta[name*='telephone'], meta[property*='telephone']")
        for meta in meta_tags:
            content = meta.get_attribute("content") or ""
            for phone in PHONE_PATTERN.findall(content):
                normalized = normalize_spanish_phone(phone)
                if normalized:
                    phones.add(normalized)
                    logging.debug(f"      Found valid phone (meta): {normalized}")

        # 4. JSON-LD structured data
        json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                content = script.inner_text()
                for phone in PHONE_PATTERN.findall(content):
                    normalized = normalize_spanish_phone(phone)
                    if normalized:
                        phones.add(normalized)
                        logging.debug(f"      Found valid phone (json-ld): {normalized}")
            except:
                pass

        # 5. Футер отдельно
        footer = page.query_selector("footer")
        if footer:
            footer_text = footer.inner_text()
            for phone in PHONE_PATTERN.findall(footer_text):
                normalized = normalize_spanish_phone(phone)
                if normalized:
                    phones.add(normalized)
                    logging.debug(f"      Found valid phone (footer): {normalized}")

    except Exception as e:
        logging.warning(f"      Error extracting phones: {e}")

    return list(phones)


def get_company_indeed_url(page):
    """Получить ссылку на страницу компании на Indeed со страницы вакансии"""
    # div[data-testid="inlineHeader-companyName"] a
    company_link = page.query_selector('div[data-testid="inlineHeader-companyName"] a')
    if company_link:
        href = company_link.get_attribute("href")
        if href:
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return "https://ar.indeed.com" + href
    return None


def get_company_website_from_indeed(page, company_indeed_url):
    """Получить сайт компании со страницы компании на Indeed"""
    if not company_indeed_url:
        return None

    logging.info(f"    [Indeed] Страница компании: {company_indeed_url[:70]}...")
    logging.info(f"Visiting company page: {company_indeed_url}")

    try:
        page.goto(company_indeed_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        # Turnstile?
        if check_for_turnstile(page):
            logging.info(f"    [Turnstile] На странице компании")
            logging.warning(f"Turnstile detected on company page")
            if not bypass_turnstile(page, "company_indeed"):
                logging.error(f"Turnstile bypass failed on company page")
                return None
            # После решения Turnstile страница перезагружается - ждем загрузки
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(1)

        # li[data-testid="companyInfo-companyWebsite"] a
        website_elem = page.query_selector('li[data-testid="companyInfo-companyWebsite"] a')
        if website_elem:
            url = website_elem.get_attribute("href")
            if url and url.startswith("http") and 'indeed.com' not in url:
                logging.info(f"    [Indeed] Сайт: {url[:70]}...")
                logging.info(f"Found company website: {url}")
                return url

        logging.info(f"    [Indeed] Сайт не найден")
        logging.info(f"Website not found on company page")
        return None

    except Exception as e:
        logging.error(f"Ошибка получения сайта: {e}")
        return None


def parse_company_website(page, website_url, company_name):
    """Парсинг сайта компании - ищем email и телефоны (без лимитов)"""
    logging.info(f"    [Web] Парсинг: {website_url[:60]}...")
    logging.info(f"Parsing company website: {website_url}")

    all_emails = set()
    all_phones = set()

    try:
        try:
            page.goto(website_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            # Игнорируем SSL ошибки и redirect loop
            error_str = str(e)
            if any(err in error_str for err in ["SSL", "SEC_ERROR", "CERT", "REDIRECT_LOOP"]):
                logging.warning(f"Connection error ignored for {website_url}: {type(e).__name__}")
                return {"emails": [], "phones": []}
            raise
        time.sleep(2)

        if check_for_turnstile(page):
            logging.warning(f"Turnstile detected on company website: {website_url}")
            if not bypass_turnstile(page, f"site_{company_name[:20]}"):
                logging.error(f"Turnstile bypass failed on website: {website_url}")
                return {"emails": [], "phones": []}
            # Ждем загрузки после редиректа
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(1)

        # Главная страница
        logging.info(f"    [Web] Парсинг главной страницы...")
        emails = extract_emails(page)
        phones = extract_phones(page)
        all_emails.update(emails)
        all_phones.update(phones)
        logging.info(f"    [Web] Главная: {len(emails)} emails, {len(phones)} телефонов")
        logging.info(f"Homepage: {len(emails)} emails, {len(phones)} phones")

        # Контактные страницы - МАКСИМАЛЬНО расширенный список
        contact_keywords = [
            # Испанский
            'contact', 'contacto', 'contacta', 'contactar', 'contactanos', 'contactenos',
            'about', 'acerca', 'sobre', 'nosotros', 'quienes-somos',
            'team', 'equipo', 'trabajadores',
            'legal', 'aviso-legal', 'avisolegal', 'terminos',
            'info', 'informacion',
            'ayuda', 'help', 'soporte', 'support',
            'empleo', 'trabajo', 'careers', 'jobs',
            'ubicacion', 'location', 'direccion',
            # Английский
            'impressum', 'imprint', 'privacy', 'privacidad',
            'terms', 'conditions', 'condiciones',
            'footer', 'pie', 'bottom'
        ]
        contact_urls = []

        # Собираем больше ссылок (до 300)
        for link in page.query_selector_all("a[href]")[:300]:
            href = link.get_attribute("href") or ""
            full_url = urljoin(website_url, href)

            # Проверяем по ключевым словам
            if any(kw in full_url.lower() for kw in contact_keywords):
                if full_url not in contact_urls and website_url in full_url:  # Только страницы этого домена
                    contact_urls.append(full_url)

        logging.info(f"    [Web] Найдено {len(contact_urls)} контактных страниц, проверю до 10")
        logging.info(f"Found {len(contact_urls)} contact pages, will check up to 10")

        # Парсим до 10 контактных страниц (с ранним выходом при достижении лимита)
        for idx, url in enumerate(contact_urls[:10], 1):
            # Останавливаемся если уже нашли достаточно контактов
            if len(all_emails) >= 3 and len(all_phones) >= 3:
                logging.info(f"    [Web] Достигнут лимит (3 emails + 3 телефона), останавливаем парсинг")
                break

            try:
                logging.info(f"    [Web] Контакт {idx}/10: {url[:60]}...")
                logging.info(f"Parsing contact page {idx}/10: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(1)

                if check_for_turnstile(page):
                    logging.warning(f"Turnstile detected on contact page")
                    if not bypass_turnstile(page, "contact"):
                        logging.error(f"Turnstile bypass failed on contact page")
                        continue
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(1)

                emails = extract_emails(page)
                phones = extract_phones(page)
                all_emails.update(emails)
                all_phones.update(phones)
                logging.info(f"    [Web] +{len(emails)} emails, +{len(phones)} телефонов (всего: {len(all_emails)} emails, {len(all_phones)} телефонов)")
                logging.info(f"Contact page {idx}: {len(emails)} emails, {len(phones)} phones")
            except Exception as e:
                logging.warning(f"Ошибка парсинга контактной страницы {idx}: {e}")

        # Возвращаем максимум 3 email и 3 телефона
        final_emails = list(all_emails)[:3]
        final_phones = list(all_phones)[:3]
        logging.info(f"    [Web] ИТОГО для сайта: {len(final_emails)} emails, {len(final_phones)} телефонов")
        logging.info(f"Total for website: {len(final_emails)} emails, {len(final_phones)} phones")

        return {"emails": final_emails, "phones": final_phones}

    except Exception as e:
        logging.error(f"Ошибка парсинга сайта {website_url}: {e}")
        return {"emails": [], "phones": []}


def parse_vacancy(page, vacancy_url, vacancy_title):
    """
    Парсинг вакансии:
    1. Открываем вакансию
    2. Находим ссылку на компанию Indeed
    3. Переходим на компанию → находим сайт
    4. Переходим на сайт → ищем emails и телефоны
    """
    result = {
        'Компания': '',
        'Телефон': '',
        'Сайт': '',
        'Email': '',
        'Ссылка на вакансию': vacancy_url,
        'Страна': 'AR'
    }

    try:
        # Название компании (страница уже открыта)
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            # Для ar.indeed.com название внутри ссылки
            company_link = company_elem.query_selector("a")
            if company_link:
                result['Компания'] = company_link.inner_text().strip()
            else:
                result['Компания'] = company_elem.inner_text().strip()
        else:
            # Пробуем альтернативные селекторы
            alt_elem = page.query_selector("[data-company-name='true']")
            if alt_elem:
                result['Компания'] = alt_elem.inner_text().strip()
            else:
                result['Компания'] = "Unknown"

        # Ссылка на компанию Indeed
        company_indeed_url = get_company_indeed_url(page)
        if not company_indeed_url:
            logging.info(f"  [!] Ссылка на компанию Indeed не найдена")
            return result

        # Получаем сайт компании со страницы Indeed
        website = get_company_website_from_indeed(page, company_indeed_url)
        if not website:
            logging.info(f"  [!] Сайт компании не найден на Indeed")
            return result

        result['Сайт'] = website

        # Парсим сайт компании - получаем emails и телефоны
        contacts = parse_company_website(page, website, result['Компания'])

        # Обрабатываем результат
        emails = contacts.get('emails', [])
        phones = contacts.get('phones', [])

        result['Email'] = "; ".join(emails) if emails else ''
        result['Телефон'] = "; ".join(phones) if phones else ''

        logging.info(f"  ИТОГО: {len(emails)} emails, {len(phones)} телефонов")

    except Exception as e:
        logging.error(f"Ошибка парсинга вакансии {vacancy_url}: {e}")

    return result


def get_company_name_from_vacancy(page, vacancy_url):
    """Быстрое извлечение только названия компании из вакансии (для проверки дубликата)"""
    try:
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        # Turnstile?
        if check_for_turnstile(page):
            if not bypass_turnstile(page, "vacancy"):
                return None

        # Название компании
        company_elem = page.query_selector("div[data-testid='inlineHeader-companyName']")
        if company_elem:
            # Для ar.indeed.com название внутри ссылки
            company_link = company_elem.query_selector("a")
            if company_link:
                return company_link.inner_text().strip()
            return company_elem.inner_text().strip()

        # Пробуем альтернативный селектор
        alt_elem = page.query_selector("[data-company-name='true']")
        if alt_elem:
            return alt_elem.inner_text().strip()

        return "Unknown"

    except Exception as e:
        logging.error(f"Ошибка извлечения компании: {e}")
        return None


# ================== ПАРСИНГ ОДНОЙ СТРАНИЦЫ ==================

def parse_single_page(browser, page_num, seen_companies):
    """
    Парсит одну страницу поиска Indeed

    Args:
        browser: Экземпляр Camoufox браузера
        page_num: Номер страницы
        seen_companies: Множество уже обработанных компаний

    Returns:
        tuple: (список данных, было ли Cloudflare challenge)
    """
    page_data = []
    had_challenge = False
    turnstile_count = 0  # Счётчик решённых Turnstile

    page = browser.new_page()
    page.set_default_timeout(30000)

    try:
        if page_num == 1:
            url = INDEED_SEARCH_URL
        else:
            url = INDEED_SEARCH_URL + f"&start={(page_num-1)*10}"

        logging.info(f"Loading: {url}")
        logging.info(f"Loading search page {page_num}: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # === ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ===
        logging.info(f"[DEBUG] Page loaded, current URL: {page.url}")
        logging.info(f"[DEBUG] Page title: {page.title()}")

        # Проверяем наличие элементов
        try:
            jobs_count = page.locator("a.jcs-JobTitle").count()
            logging.info(f"[DEBUG] Found {jobs_count} job title elements on page")
        except Exception as e:
            logging.error(f"[DEBUG] Error counting job titles: {e}")

        # Сохраняем HTML и скриншот для анализа
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
        # === КОНЕЦ ДЕТАЛЬНОГО ЛОГИРОВАНИЯ ===

        # Проверяем Cloudflare Challenge (не Turnstile)
        current_url = page.url
        page_title = page.title()

        if '__cf_chl_rt_tk=' in current_url or 'Control de seguridad' in page_title or 'Un momento' in page_title:
            had_challenge = True
            logging.info(f"[Cloudflare] Обнаружен Cloudflare Challenge! Title: {page_title}")
            logging.warning(f"Cloudflare Challenge detected on page {page_num}")

            # ПЫТАЕМСЯ ПРОЙТИ TURNSTILE
            logging.info("[Cloudflare] Попытка пройти Turnstile чекбокс...")
            if bypass_turnstile(page, f"cloudflare_challenge_page{page_num}"):
                logging.info("[Cloudflare] ✓ Turnstile пройден!")
                # Ждем загрузки контента после прохождения
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(2)
            else:
                logging.warning("[Cloudflare] Turnstile не удалось пройти, ждем автоматического разрешения...")
                # Если не удалось пройти - ждем автоматического разрешения (до 30 секунд)
                max_wait = 30
                for i in range(max_wait):
                    time.sleep(1)
                    current_url = page.url
                    page_title = page.title()

                    # Проверяем, разрешился ли Challenge
                    if '__cf_chl_rt_tk=' not in current_url and 'Control de seguridad' not in page_title and 'Un momento' not in page_title:
                        logging.info(f"[Cloudflare] ✓ Challenge разрешен за {i+1}с!")
                        logging.info(f"Cloudflare Challenge resolved after {i+1}s")
                        break
                else:
                    # Если не разрешился за 30 секунд - попробуем перезагрузить
                    logging.warning(f"[Cloudflare] Challenge не разрешился за {max_wait}с, перезагрузка страницы...")
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=60000)
                        time.sleep(3)

                        current_url = page.url
                        page_title = page.title()

                        if '__cf_chl_rt_tk=' in current_url or 'Control de seguridad' in page_title:
                            logging.error("[Cloudflare] ✗ Challenge не разрешился даже после перезагрузки")
                            return [], had_challenge
                        else:
                            logging.info("[Cloudflare] ✓ Challenge разрешен после перезагрузки")
                    except Exception as e:
                        logging.error(f"[Cloudflare] Ошибка при перезагрузке: {e}")
                        return [], had_challenge

            # После разрешения ждем загрузки контента
            time.sleep(2)

        # Проверяем Turnstile (до 5 раз)
        max_turnstile_attempts = 5
        for attempt in range(max_turnstile_attempts):
            if check_for_turnstile(page):
                had_challenge = True
                turnstile_count += 1

                logging.info(f"[Turnstile #{turnstile_count}] Обнаружен на странице поиска!")
                logging.warning(f"Turnstile #{turnstile_count} detected on search page {page_num}")

                if not bypass_turnstile(page, f"search_page_{page_num}_attempt{turnstile_count}"):
                    logging.info(f"[Turnstile #{turnstile_count}] ✗ Не удалось решить!")
                    logging.error(f"Turnstile bypass failed on search page (attempt {turnstile_count})")
                    return [], had_challenge

                # После решения ждем загрузки с увеличенным таймаутом
                logging.info(f"[Turnstile #{turnstile_count}] Ожидание загрузки (увеличенный таймаут 30с)...")
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                time.sleep(15)  # Увеличено с 2 до 15 секунд

                logging.info(f"[Turnstile #{turnstile_count}] Текущий URL: {page.url[:80]}")
                logging.info(f"[Turnstile #{turnstile_count}] Заголовок: {page.title()}")
            else:
                # Нет больше Turnstile
                break

        # Если решили 3+ Turnstile, делаем ручной переход на целевой URL
        if turnstile_count >= 3:
            logging.info(f"\n{'='*80}")
            logging.info(f"[MANUAL REDIRECT] Решено {turnstile_count} Turnstile!")
            logging.info(f"[MANUAL REDIRECT] Делаем ручной переход на целевой URL...")
            logging.info(f"{'='*80}\n")

            try:
                # Принудительно переходим на целевой URL
                logging.info(f"[MANUAL REDIRECT] Переход на: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(10)  # Даём время на полную загрузку

                logging.info(f"[MANUAL REDIRECT] ✓ Переход выполнен!")
                logging.info(f"[MANUAL REDIRECT] Новый URL: {page.url[:80]}")
                logging.info(f"[MANUAL REDIRECT] Заголовок: {page.title()}")

                # Сохраняем скриншот и HTML после ручного перехода
                try:
                    manual_redirect_html = results_dir / f"manual_redirect_page{page_num}.html"
                    manual_redirect_screenshot = results_dir / f"manual_redirect_page{page_num}.png"

                    with open(manual_redirect_html, 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    page.screenshot(path=str(manual_redirect_screenshot))

                    logging.info(f"[MANUAL REDIRECT] Сохранены: {manual_redirect_html.name}, {manual_redirect_screenshot.name}")
                except Exception as e:
                    logging.warning(f"[MANUAL REDIRECT] Ошибка сохранения файлов: {e}")

            except Exception as e:
                logging.error(f"[MANUAL REDIRECT] ✗ Ошибка перехода: {e}")
                return [], had_challenge

        # Проверяем финальный URL
        current_url = page.url
        if 'secure.indeed.com/auth' in current_url:
            logging.info(f"[ERROR] Редирект на авторизацию: {current_url[:80]}...")
            logging.error(f"Redirected to login page: {current_url}")

            # Пытаемся повторно залогиниться через cookies
            if relogin_with_cookies(page, url):
                logging.info(f"[Auth] ✓ Повторный логин успешен, продолжаем парсинг страницы {page_num}")
                # Проверяем еще раз URL после логина
                current_url = page.url
                if 'secure.indeed.com/auth' in current_url:
                    logging.error(f"[Auth] ✗ Повторный логин не помог")
                    return [], had_challenge
            else:
                logging.error(f"[Auth] ✗ Повторный логин не удался")
                return [], had_challenge

        # Сохраняем скриншот и HTML для отладки
        try:
            debug_path = results_dir / f"debug_page{page_num}.png"
            page.screenshot(path=str(debug_path))

            html_path = results_dir / f"debug_page{page_num}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
        except Exception as e:
            logging.info(f"[DEBUG] Ошибка сохранения отладочных файлов: {e}")

        # Ждём появления ссылок на вакансии (увеличенный таймаут для Interactive Challenge)
        logging.info("[WAITING] Ожидание появления вакансий (таймаут 60с)...")
        page.wait_for_selector("a.jcs-JobTitle", timeout=60000)

        # Собираем ссылки на вакансии
        vacancy_links = []
        for link_elem in page.query_selector_all("a.jcs-JobTitle"):
            title = link_elem.inner_text().strip()
            href = link_elem.get_attribute("href")
            if href:
                full_url = "https://ar.indeed.com" + href if href.startswith("/") else href
                vacancy_links.append({'title': title, 'url': full_url})

        logging.info(f"\nFound {len(vacancy_links)} vacancies\n")
        logging.info(f"Page {page_num}: found {len(vacancy_links)} vacancies")

        # Парсим каждую вакансию
        for idx, vac in enumerate(vacancy_links, 1):
            logging.info(f"\n[{idx}/{len(vacancy_links)}] {'-'*60}")
            logging.info(f"  Вакансия: {vac['title'][:60]}...")
            logging.info(f"  URL: {vac['url'][:80]}...")

            logging.info(f"Processing vacancy {idx}/{len(vacancy_links)}: {vac['title'][:50]}")

            # Извлекаем название компании
            company_name = get_company_name_from_vacancy(page, vac['url'])
            if not company_name:
                logging.info(f"  [!] Не удалось извлечь компанию")
                logging.warning(f"Failed to extract company name from: {vac['url']}")
                continue

            logging.info(f"  Компания: {company_name}")
            logging.info(f"Company: {company_name}")

            # Проверка на дубликат
            company_key = company_name.lower().strip()
            if company_key in seen_companies:
                logging.info(f"  [SKIP] Компания уже обработана!")
                logging.info(f"Skipping duplicate company: {company_name}")
                continue

            # Парсим вакансию полностью
            data = parse_vacancy(page, vac['url'], vac['title'])
            seen_companies.add(company_key)
            page_data.append(data)

            emails_count = len(data['Email'].split("; ")) if data['Email'] else 0
            phones_count = len(data['Телефон'].split("; ")) if data['Телефон'] else 0
            logging.info(f"Parsed {company_name}: website={bool(data['Сайт'])}, emails={emails_count}, phones={phones_count}")

            time.sleep(2)

    except Exception as e:
        logging.error(f"Error parsing page {page_num}: {e}")
        logging.info(f"[ERROR] Ошибка парсинга страницы: {e}")

    finally:
        page.close()

    return page_data, had_challenge


# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ MAIN ==================

class BrowserContext:
    """Контекст для управления браузером с прокси"""
    def __init__(self, proxy_config=None):
        self.proxy_config = proxy_config
        self.camoufox_params = {
            'headless': False if platform.system() == "Linux" else HEADLESS_MODE,  # NO headless на Linux для WebGL
            'humanize': True,
            'os': 'windows',
            'locale': 'es-ES',
            'geoip': False,  # Отключаем geoip проверку из-за проблем с аутентификацией

            # STEALTH MODE: Подмена fingerprint для обхода Cloudflare
            'addons': [],  # Пока пусто, можно добавить расширения
        }

        if proxy_config:
            self.camoufox_params['proxy'] = proxy_config

        self._camoufox = None
        self._browser = None

    def __enter__(self):
        self._camoufox = Camoufox(**self.camoufox_params)
        self._browser = self._camoufox.__enter__()

        # STEALTH INJECTIONS: Подменяем fingerprint ДО создания страниц
        self._inject_stealth_scripts()

        return self._browser

    def _inject_stealth_scripts(self):
        """Внедряем JavaScript для подмены fingerprint"""
        if not self._browser:
            return

        # JavaScript для подмены fingerprint - применяется ко ВСЕМ новым страницам
        stealth_js = """
        // STEALTH MODE: Расширенная подмена fingerprint для обхода Cloudflare

        // 1. Подмена navigator.hardwareConcurrency с 22 на 6 ядер
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 6,
            configurable: true
        });

        // 2. Подмена Date.prototype.getTimezoneOffset для Europe/Madrid (UTC+1)
        const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {
            return -60; // UTC+1 (зимнее время в Испании)
        };

        // 3. УЛУЧШЕННЫЙ WebGL stealth - пробуем создать контекст с fallback
        // Сохраняем оригинальный getContext
        const originalGetContext = HTMLCanvasElement.prototype.getContext;

        // Переопределяем getContext для подмены WebGL
        HTMLCanvasElement.prototype.getContext = function(contextType, ...args) {
            // Для webgl/webgl2 пытаемся получить реальный контекст
            if (contextType === 'webgl' || contextType === 'webgl2' || contextType === 'experimental-webgl') {
                const gl = originalGetContext.call(this, contextType, ...args);

                // Если контекст создан успешно - патчим getParameter
                if (gl) {
                    const originalGetParameter = gl.getParameter.bind(gl);
                    gl.getParameter = function(parameter) {
                        // UNMASKED_VENDOR_WEBGL (37445)
                        if (parameter === 37445) {
                            return 'Google Inc. (NVIDIA)';
                        }
                        // UNMASKED_RENDERER_WEBGL (37446)
                        if (parameter === 37446) {
                            return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)';
                        }
                        return originalGetParameter(parameter);
                    };
                }

                return gl;
            }

            // Для других контекстов - возвращаем как есть
            return originalGetContext.call(this, contextType, ...args);
        };

        // 4. Добавляем window.chrome object (признак Chrome-based браузера)
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }

        // 5. Скрываем следы автоматизации в Permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = function(parameters) {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: 'prompt' });
            }
            return originalQuery.call(window.navigator.permissions, parameters);
        };

        // 6. Добавляем Battery API (признак реального устройства)
        if (!navigator.getBattery) {
            navigator.getBattery = function() {
                return Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 0.87,
                    addEventListener: function() {},
                    removeEventListener: function() {},
                    dispatchEvent: function() {}
                });
            };
        }

        console.log('[STEALTH] Enhanced fingerprint injections applied: CPU=6, WebGL=NVIDIA GTX 1060, TZ=Madrid, Chrome APIs');
        """

        # ================== WEBRTC LEAK PROTECTION ==================
        # Блокируем утечку IP через WebRTC при использовании VPN/Proxy
        webrtc_block_script = """
        (() => {
            // Проверяем, что скрипт выполняется только один раз
            if (window.hasRunWebRTCBlock) return;
            window.hasRunWebRTCBlock = true;

            // Сохраняем оригинальный RTCPeerConnection
            const OriginalRTCPeerConnection = window.RTCPeerConnection ||
                                              window.mozRTCPeerConnection ||
                                              window.webkitRTCPeerConnection;

            if (!OriginalRTCPeerConnection) {
                console.log('[WEBRTC] RTCPeerConnection not found, skipping');
                return;
            }

            // Переопределяем RTCPeerConnection для блокировки утечки IP
            function RTCPeerConnectionModified(config, constraints) {
                // КРИТИЧНО: Очищаем iceServers - это предотвращает утечку реального IP
                if (config && config.iceServers) {
                    // Оставляем пустой массив - это блокирует получение внешнего IP через STUN
                    config.iceServers = [];
                }

                // Создаём оригинальное соединение с модифицированной конфигурацией
                return new OriginalRTCPeerConnection(config, constraints);
            }

            // Копируем прототип для совместимости
            RTCPeerConnectionModified.prototype = OriginalRTCPeerConnection.prototype;

            // Заменяем глобальные объекты
            window.RTCPeerConnection = RTCPeerConnectionModified;
            window.mozRTCPeerConnection = RTCPeerConnectionModified;
            window.webkitRTCPeerConnection = RTCPeerConnectionModified;

            // Опционально: блокируем getUserMedia (камера/микрофон) для дополнительной анонимности
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                navigator.mediaDevices.getUserMedia = function(constraints) {
                    console.log('[WEBRTC] getUserMedia call blocked');
                    return Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));
                };
            }

            console.log('[WEBRTC BLOCK] ✓ WebRTC leak protection enabled - IP leak prevented');
        })();
        """

        # Получаем или создаём контекст для инъекций
        if self._browser.contexts:
            context = self._browser.contexts[0]
        else:
            context = self._browser.new_context()

        # Добавляем скрипты к контексту (будет применён ко всем новым страницам)
        context.add_init_script(stealth_js)
        context.add_init_script(webrtc_block_script)
        logging.info("[STEALTH] Enhanced fingerprint injections enabled: hardwareConcurrency=6, timezone=Madrid, WebGL=NVIDIA, Chrome APIs, Battery API")
        logging.info("[WEBRTC] WebRTC leak protection enabled - IP address will not leak through WebRTC")

    def __exit__(self, *args):
        if self._camoufox:
            self._camoufox.__exit__(*args)

    def close(self):
        """Закрыть браузер"""
        if self._camoufox:
            self._camoufox.__exit__(None, None, None)
            self._camoufox = None
            self._browser = None


def create_browser_with_proxy(proxy_config=None):
    """Создать контекст браузера с указанным прокси"""
    return BrowserContext(proxy_config)


def close_browser_safely(browser):
    """Безопасно закрыть браузер с контекстом"""
    if browser is None:
        return

    # Если у браузера есть сохранённый контекст - закрываем через него
    if hasattr(browser, '_browser_context'):
        browser._browser_context.close()
    else:
        # Иначе пробуем закрыть напрямую
        try:
            browser.close()
        except Exception as e:
            logging.warning(f"Error closing browser: {e}")


def relogin_with_cookies(page, target_url):
    """
    Повторная авторизация через cookies при редиректе на логин

    Args:
        page: текущая страница
        target_url: целевой URL, на который пытались попасть

    Returns:
        bool: True если успешно залогинились и вернулись на target_url
    """
    try:
        logging.warning(f"[Auth] Требуется авторизация, попытка автологина через cookies...")

        # Загружаем cookies из файла
        cookies_file = "indeed_cookies.json"
        try:
            cookies = load_cookies_from_json(cookies_file)
            logging.info(f"[Auth] Загружено {len(cookies)} cookies из {cookies_file}")
        except Exception as e:
            logging.error(f"[Auth] Не удалось загрузить cookies: {e}")
            return False

        # Применяем cookies к текущему контексту
        context = page.context
        try:
            apply_cookies_to_context(context, cookies)
            logging.info(f"[Auth] Cookies применены к контексту")
        except Exception as e:
            logging.error(f"[Auth] Не удалось применить cookies: {e}")
            return False

        # Пробуем снова перейти на целевой URL
        logging.info(f"[Auth] Переход на целевой URL: {target_url[:80]}...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Проверяем, удалось ли избежать редиректа на авторизацию
        current_url = page.url
        if 'secure.indeed.com/auth' in current_url:
            logging.error(f"[Auth] ✗ Cookies не помогли, снова редирект на авторизацию")
            return False

        logging.info(f"[Auth] ✓ Успешно залогинились! Текущий URL: {current_url[:80]}...")
        return True

    except Exception as e:
        logging.error(f"[Auth] Ошибка при попытке повторного логина: {e}")
        return False


def warmup_browser(browser):
    """Прогрев браузера - посещает популярные сайты"""
    try:
        logging.info("  [Прогрев] google.es...")
        page = browser.new_page()
        page.goto("https://www.google.es", wait_until="domcontentloaded", timeout=60000)
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
        logging.info("Browser warmup completed")
    except Exception as e:
        logging.warning(f"Browser warmup failed: {e}")
        logging.info(f"  [Прогрев] Ошибка, но продолжаем...\n")


# ================== MAIN С УМНОЙ РОТАЦИЕЙ ПРОКСИ ==================

def main():
    logging.info("\n" + "="*80)
    logging.info("Indeed Parser v5.0 - WITH SMART PROXY ROTATION")
    logging.info(f"Results: {results_dir}")
    logging.info("="*80 + "\n")
    logging.info("Parser v5.0 started with smart proxy rotation")

    # Отправка стартового сообщения на webhook
    payload = {
        "message": "Скрипт indeed.ar активирован!",
        "time": datetime.now(kiev_tz).strftime("%Y-%m-%d %H:%M:%S")
    }
    send_webhook(WEBHOOK_START_URL, payload)

    all_data = []
    seen_companies = set()

    # ================== ИНИЦИАЛИЗАЦИЯ РОТАЦИИ ПРОКСИ ==================
    # ПРОКСИ ОТКЛЮЧЕНЫ - ротация закомментирована
    # global proxy_rotation_manager
    # proxy_rotation_manager = None
    #
    # if USE_PROXIES and proxy_manager:
    #     proxy_rotation_manager = ProxyRotationManager(
    #         proxy_manager=proxy_manager,
    #         rotation_interval=3,  # Менять прокси каждые 3 страницы
    #         max_challenges=3      # Менять после 3 challenge подряд
    #     )
    #     logging.info(f"  [Proxy] Умная ротация включена:")
    #     logging.info(f"           - Каждые 3 страницы")
    #     logging.info(f"           - После 3 Cloudflare challenge подряд")
    #     logging.info("Smart proxy rotation enabled")

    # proxy_rotation_manager = None  # Прокси отключены

    # ================== ЦИКЛ ПАРСИНГА БЕЗ ПРОКСИ (было: С РОТАЦИЕЙ) ==================
    current_browser = None
    # current_proxy = None  # Не используется без прокси
    first_browser = True  # Флаг для первого браузера (нужен для прогрева)

    for page_num in range(1, PAGES_TO_PARSE + 1):
        logging.info(f"\n{'='*80}")
        logging.info(f"PAGE {page_num}/{PAGES_TO_PARSE}")
        logging.info(f"{'='*80}\n")

        # Проверяем, нужно ли создать/сменить браузер
        # ПРОКСИ ОТКЛЮЧЕНЫ - создаем браузер только один раз
        # need_new_browser = False
        #
        # if proxy_rotation_manager:
        #     # Получаем текущий прокси
        #     current_proxy = proxy_rotation_manager.get_current_proxy()
        #
        #     # Для первой страницы создаём браузер
        #     if current_browser is None:
        #         need_new_browser = True
        #         logging.info(f"  [Proxy] Создаём браузер с прокси: {current_proxy['server']}")
        #         logging.info(f"Creating browser with proxy: {current_proxy['server']}")

        # Создаём новый браузер если нужно (только один раз с прокси)
        if current_browser is None:
            # Используем ROTATING ENDPOINT для Residential прокси
            if USE_PROXIES:
                proxy_config = {
                    'server': 'p.webshare.io:80',
                    'username': 'dbgrpsyu-ES-rotate',  # Формат: base-COUNTRY-rotate для испанских IP
                    'password': 'YOUR_PASSWORD'
                }
                logging.info(f"✅ [Proxy] Using ROTATING RESIDENTIAL endpoint: {proxy_config['server']}")
                logging.info(f"✅ [Proxy] Username: {proxy_config['username']} (Spain only)")
                browser_context = create_browser_with_proxy(proxy_config)
            else:
                # Создаём контекст браузера без прокси
                browser_context = create_browser_with_proxy(None)

            # Входим в контекст и получаем реальный браузер
            current_browser = browser_context.__enter__()
            # Сохраняем ссылку на контекст для корректного закрытия
            current_browser._browser_context = browser_context

            # Прогреваем только первый браузер
            if first_browser:
                warmup_browser(current_browser)
                first_browser = False

                # ================== ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ СЕТИ ==================
                logging.info("\n🔍 Starting detailed network logging...")
                network_logger = NetworkLogger()

                # Создаём тестовую страницу для логирования
                test_page = current_browser.new_page()
                try:
                    # Переходим на простую страницу для проверки
                    test_page.goto("https://www.google.es", wait_until="domcontentloaded", timeout=60000)
                    time.sleep(2)

                    # Получаем конфиг прокси если есть
                    proxy_config = None
                    if USE_PROXIES:
                        # Используем ротационный endpoint
                        proxy_config = {
                            'server': 'p.webshare.io:80',
                            'username': 'dbgrpsyu-ES-rotate',
                            'password': 'YOUR_PASSWORD'
                        }

                    # Логируем полное состояние сети
                    network_logger.log_full_network_state(
                        page=test_page,
                        proxy_config=proxy_config,
                        url="https://www.google.es"
                    )

                except Exception as e:
                    logging.error(f"❌ Ошибка детального логирования: {e}")
                finally:
                    test_page.close()

                logging.info("✅ Detailed network logging completed\n")
                # ================== КОНЕЦ ДЕТАЛЬНОГО ЛОГИРОВАНИЯ ==================

        # ================== ПАРСИМ СТРАНИЦУ ==================
        page_data, had_challenge = parse_single_page(current_browser, page_num, seen_companies)
        all_data.extend(page_data)

        # ================== ПРОВЕРЯЕМ РОТАЦИЮ ==================
        # ПРОКСИ ОТКЛЮЧЕНЫ - ротация закомментирована
        # if proxy_rotation_manager:
        #     if proxy_rotation_manager.should_rotate(had_challenge=had_challenge):
        #         # Нужно сменить прокси
        #         old_proxy = current_proxy
        #         new_proxy = proxy_rotation_manager.rotate_proxy()
        #
        #         logging.info(f"\n{'='*80}")
        #         logging.info(f"[PROXY ROTATION]")
        #         logging.info("="*80)
        #         logging.info(f"  Старый прокси: {old_proxy['server']}")
        #         logging.info(f"  Новый прокси:  {new_proxy['server']}")
        #         if had_challenge:
        #             logging.info(f"  Причина:      Много Cloudflare challenge ({proxy_rotation_manager.challenge_count + 1})")
        #         else:
        #             logging.info(f"  Причина:      Ротация по счётчику (каждые 3 страницы)")
        #         logging.info(f"  Всего ротаций: {proxy_rotation_manager.total_rotations}")
        #         logging.info(f"{'='*80}\n")
        #
        #         # Закрываем браузер - будет создан новый на следующей итерации
        #         close_browser_safely(current_browser)
        #         current_browser = None
        #         time.sleep(3)  # Пауза перед новым браузером

    # Закрываем последний браузер
    if current_browser:
        close_browser_safely(current_browser)

    # ================== СТАТИСТИКА РОТАЦИИ ==================
    # ПРОКСИ ОТКЛЮЧЕНЫ - статистика закомментирована
    # if proxy_rotation_manager:
    #     stats = proxy_rotation_manager.get_stats()
    #     logging.info(f"\n{'='*80}")
    #     logging.info(f"[СТАТИСТИКА РОТАЦИИ ПРОКСИ]")
    #     logging.info("="*80)
    #     logging.info(f"  Всего ротаций:      {stats['total_rotations']}")
    #     logging.info(f"  Страниц обработано: {stats['pages_processed']}")
    #     logging.info(f"  Финальный прокси:   {stats['current_proxy']}")
    #     logging.info(f"{'='*80}\n")
    #     logging.info(f"Proxy rotation stats: rotations={stats['total_rotations']}, pages={stats['pages_processed']}")

    # ================== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ==================
    logging.info(f"\n{'='*80}")
    logging.info("SAVING RESULTS")
    logging.info(f"{'='*80}\n")
    logging.info("Starting final data processing and saving")

    # Дедупликация по названию компании
    seen_companies_dict = {}
    deduped_data = []
    for item in all_data:
        company_name = item['Компания'].lower().strip()
        if company_name not in seen_companies_dict:
            seen_companies_dict[company_name] = item
            deduped_data.append(item)
        else:
            # Объединяем emails
            existing = seen_companies_dict[company_name]
            existing_emails = set(existing['Email'].split("; ")) if existing['Email'] else set()
            new_emails = set(item['Email'].split("; ")) if item['Email'] else set()
            existing['Email'] = "; ".join(sorted(existing_emails | new_emails))

    duplicates_removed = len(all_data) - len(deduped_data)
    if duplicates_removed > 0:
        logging.info(f"\nУдалено дубликатов компаний: {duplicates_removed}")
        logging.info(f"Removed {duplicates_removed} duplicate companies")
    all_data = deduped_data

    # Проверка данных
    if not all_data:
        logging.info("\n⚠️  Нет данных для сохранения!")
        logging.warning("No data to save")
        return

    # Сохранение в Excel
    df = pd.DataFrame(all_data)
    cols = ['Компания', 'Телефон', 'Сайт', 'Email', 'Ссылка на вакансию', 'Страна']
    df = df[cols]

    excel_file = results_dir / f"indeed_results_{current_time}.xlsx"
    df.to_excel(excel_file, index=False, engine='openpyxl')
    logging.info(f"Saved Excel: {excel_file.name}")

    # Автоподстройка ширины столбцов
    wb = load_workbook(excel_file)
    ws = wb.active
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        adjusted_width = length + 2
        ws.column_dimensions[column_cells[0].column_letter].width = adjusted_width
    wb.save(excel_file)

    # Статистика
    total = len(all_data)
    with_emails = len([d for d in all_data if d['Email']])
    with_phones = len([d for d in all_data if d['Телефон']])
    with_websites = len([d for d in all_data if d['Сайт']])
    total_emails = sum(len(d['Email'].split("; ")) for d in all_data if d['Email'])
    total_phones = sum(len(d['Телефон'].split("; ")) for d in all_data if d['Телефон'])

    logging.info(f"Total vacancies:   {total}")
    logging.info(f"With websites:     {with_websites} ({with_websites/total*100:.1f}%)")
    logging.info(f"With emails:       {with_emails} ({with_emails/total*100:.1f}%)")
    logging.info(f"With phones:       {with_phones} ({with_phones/total*100:.1f}%)")
    logging.info(f"Total emails:      {total_emails}")
    logging.info(f"Total phones:      {total_phones}")
    logging.info(f"\nSaved: {excel_file.name}")

    logging.info(f"=== FINAL STATISTICS ===")
    logging.info(f"Total: {total}, Websites: {with_websites}, Emails: {total_emails}, Phones: {total_phones}")
    logging.info(f"Results saved to: {excel_file.name}")

    # ================== ОТПРАВКА НА WEBHOOK ==================
    logging.info(f"\n{'='*80}")
    logging.info("ОТПРАВКА НА WEBHOOK")
    logging.info(f"{'='*80}\n")

    webhook_payload = {
        "source": "indeed.ar",
        "data": all_data
    }

    if send_webhook(WEBHOOK_RESULTS_URL, webhook_payload, timeout=30):
        logging.info(f"✅ Всего компаний отправлено: {len(all_data)}")
    else:
        logging.info(f"⚠️ Ошибка отправки на webhook")

    logging.info(f"\n{'='*80}\n")
    logging.info(f"Done: {total} vacancies, {with_websites} websites, {total_emails} emails, {total_phones} phones")

if __name__ == "__main__":
    main()
