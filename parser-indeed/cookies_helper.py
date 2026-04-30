#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookies Helper для Indeed Parser

Помогает загружать cookies из JSON файла и применять их в Camoufox
"""

import json
import logging
from pathlib import Path


def load_cookies_from_json(cookies_file="indeed_cookies.json"):
    """
    Загрузить cookies из JSON файла

    Формат файла (массив объектов):
    [
        {
            "name": "CTK",
            "value": "1ht...",
            "domain": ".indeed.com",
            "path": "/",
            "expires": 1234567890,
            "httpOnly": false,
            "secure": true
        },
        ...
    ]

    Или формат Netscape (cookies.txt) - автоматически конвертируется
    """
    cookies_path = Path(cookies_file)

    if not cookies_path.exists():
        logging.warning(f"Cookies file not found: {cookies_file}")
        return []

    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

            # Проверяем формат
            if content.startswith('['):
                # JSON формат
                cookies = json.loads(content)
            elif content.startswith('{'):
                # Один объект cookie
                cookies = [json.loads(content)]
            else:
                # Возможно, текстовый формат
                logging.error(f"Unsupported cookies format in {cookies_file}")
                return []

        logging.info(f"Loaded {len(cookies)} cookies from {cookies_file}")
        return cookies

    except Exception as e:
        logging.error(f"Failed to load cookies: {e}")
        return []


def apply_cookies_to_context(context, cookies):
    """
    Применить cookies к Playwright context

    Args:
        context: Playwright browser context
        cookies: Список cookies в формате Playwright
    """
    if not cookies:
        logging.warning("No cookies to apply")
        return False

    try:
        # Playwright требует специфичный формат
        playwright_cookies = []

        for cookie in cookies:
            # Конвертируем в формат Playwright если нужно
            pc = {
                'name': cookie.get('name', ''),
                'value': cookie.get('value', ''),
                'domain': cookie.get('domain', '.indeed.com'),
                'path': cookie.get('path', '/'),
            }

            # Опциональные поля
            if 'expires' in cookie and cookie['expires']:
                pc['expires'] = cookie['expires']
            if 'httpOnly' in cookie:
                pc['httpOnly'] = cookie['httpOnly']
            if 'secure' in cookie:
                pc['secure'] = cookie['secure']

            # sameSite требует точные значения: Strict, Lax, или None
            if 'sameSite' in cookie and cookie['sameSite']:
                same_site = cookie['sameSite'].lower()
                # Нормализуем значение
                if same_site in ['strict', 'lax', 'none']:
                    pc['sameSite'] = same_site.capitalize() if same_site != 'none' else 'None'
                elif same_site in ['no_restriction', 'unspecified']:
                    # Браузерные экспорты могут использовать эти значения
                    pc['sameSite'] = 'None'
                else:
                    # Если значение некорректное, используем Lax по умолчанию
                    pc['sameSite'] = 'Lax'

            playwright_cookies.append(pc)

        # Применяем cookies
        context.add_cookies(playwright_cookies)
        logging.info(f"Applied {len(playwright_cookies)} cookies to browser context")
        return True

    except Exception as e:
        logging.error(f"Failed to apply cookies: {e}")
        return False


def save_cookies_template(output_file="indeed_cookies_template.json"):
    """
    Создать шаблон файла cookies для пользователя
    """
    template = [
        {
            "name": "CTK",
            "value": "ваш_токен_сюда",
            "domain": ".indeed.com",
            "path": "/",
            "httpOnly": False,
            "secure": True
        },
        {
            "name": "INDEED_CSRF_TOKEN",
            "value": "ваш_csrf_токен",
            "domain": ".indeed.com",
            "path": "/",
            "httpOnly": False,
            "secure": True
        }
    ]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"Template created: {output_file}")
    print("Экспортируйте cookies из браузера и замените этот файл")


if __name__ == "__main__":
    # Создаем шаблон
    save_cookies_template()
