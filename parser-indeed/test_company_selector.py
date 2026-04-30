"""
Тестовый скрипт для определения правильного селектора компании на ar.indeed.com
"""

import os
import sys
import time
from camoufox.sync_api import Camoufox

# Добавляем путь для импорта cookies_helper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cookies_helper import load_cookies_from_json, apply_cookies_to_context

INDEED_SEARCH_URL = "https://ar.indeed.com/jobs?q=Call+Center&l="
COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'indeed_cookies.json')

def test_company_selector():
    """Тестируем различные селекторы для извлечения названия компании"""

    print("\n" + "="*80)
    print("ТЕСТ СЕЛЕКТОРОВ КОМПАНИИ ДЛЯ ARGENTINA INDEED")
    print("="*80 + "\n")

    # Загружаем cookies
    cookies = load_cookies_from_json(COOKIES_FILE)
    if not cookies:
        print("[FAIL] Не удалось загрузить cookies")
        return

    print(f"[OK] Cookies загружены: {len(cookies)} штук\n")

    # Запускаем браузер
    with Camoufox(
        headless=False,  # С GUI для просмотра
        humanize=True,
        exclude_addons=['uBlock0@raymondhill.net'],
        os="windows",
        screen=("1920x1080", 24),
        geoip=True,
        block_images=False,
        block_webrtc=True
    ) as browser:

        context = browser.contexts[0]
        page = browser.pages[0]

        # Применяем cookies
        apply_cookies_to_context(context, cookies)
        print("[OK] Cookies применены\n")

        # Переходим на страницу поиска
        print(f"Открываем: {INDEED_SEARCH_URL}")
        page.goto(INDEED_SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Получаем первую вакансию
        print("Ищем первую вакансию...")
        vacancy_links = page.query_selector_all("a[data-jk]")

        if not vacancy_links:
            print("[FAIL] Вакансии не найдены!")
            return

        first_vacancy_link = vacancy_links[0]
        vacancy_url = first_vacancy_link.get_attribute("href")
        if not vacancy_url.startswith("http"):
            vacancy_url = "https://ar.indeed.com" + vacancy_url

        print(f"[OK] Найдена вакансия: {vacancy_url}\n")

        # Открываем вакансию
        print("Открываем вакансию...")
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        print("\n" + "="*80)
        print("ТЕСТИРУЕМ СЕЛЕКТОРЫ:")
        print("="*80 + "\n")

        # Список селекторов для тестирования
        selectors = [
            "div[data-testid='inlineHeader-companyName']",  # Испанский вариант
            "div[data-company-name='true']",
            "span[data-testid='company-name']",
            "a[data-testid='company-name']",
            ".css-1saizt3.e1wnkr790",  # Возможный CSS класс
            ".companyName",
            "[data-company-name]",
            "div.jobsearch-InlineCompanyRating > div:first-child",
            "div.jobsearch-CompanyInfoContainer > div:first-child",
        ]

        results = {}

        for selector in selectors:
            try:
                elem = page.query_selector(selector)
                if elem:
                    text = elem.inner_text().strip()
                    results[selector] = text
                    print(f"[OK] {selector}")
                    print(f"   Текст: '{text}'\n")
                else:
                    print(f"[FAIL] {selector} - не найден\n")
            except Exception as e:
                print(f"[FAIL] {selector} - ошибка: {e}\n")

        # Сохраняем HTML для ручного анализа
        html_content = page.content()
        html_file = os.path.join(os.path.dirname(__file__), 'vacancy_debug.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print("="*80)
        print(f"HTML сохранен в: {html_file}")
        print("="*80 + "\n")

        if results:
            print("[OK] НАЙДЕННЫЕ СЕЛЕКТОРЫ:")
            for selector, text in results.items():
                print(f"  {selector}: '{text}'")
        else:
            print("[FAIL] НИ ОДИН СЕЛЕКТОР НЕ СРАБОТАЛ!")
            print("Нужно вручную проанализировать HTML в vacancy_debug.html")

        print("\nБраузер остается открытым 30 секунд для ручной проверки...")
        time.sleep(30)

if __name__ == "__main__":
    test_company_selector()
