"""Простой скрипт для получения HTML одной вакансии"""
import time
from camoufox.sync_api import Camoufox

with Camoufox(headless=True, humanize=True, geoip=True, block_webrtc=True) as browser:
    page = browser.new_page()

    # Открываем поиск
    page.goto("https://ar.indeed.com/jobs?q=Call+Center&l=", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # Получаем первую вакансию
    vacancy_links = page.query_selector_all("a[data-jk]")
    if vacancy_links:
        vacancy_url = vacancy_links[0].get_attribute("href")
        if not vacancy_url.startswith("http"):
            vacancy_url = "https://ar.indeed.com" + vacancy_url

        print(f"Открываем: {vacancy_url}")

        # Открываем вакансию
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Сохраняем HTML
        html = page.content()
        with open('vacancy_argentina.html', 'w', encoding='utf-8') as f:
            f.write(html)

        # Сохраняем скриншот
        page.screenshot(path='vacancy_argentina.png', full_page=True)

        print("Сохранено: vacancy_argentina.html и vacancy_argentina.png")
