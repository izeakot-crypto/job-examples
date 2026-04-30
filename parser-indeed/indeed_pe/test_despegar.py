#!/usr/bin/env python3
"""Тест на конкретній компанії Despegar"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import time
from camoufox.sync_api import Camoufox
from pathlib import Path

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
print("ТЕСТ: Despegar.com")
print("="*60)

Path("debug_results").mkdir(exist_ok=True)

with Camoufox(headless=True, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()

    page.goto("https://www.google.com.pe", timeout=30000)
    time.sleep(2)

    # Сторінка компанії Despegar
    print("\n[1] Завантаження сторінки компанії Despegar...")
    page.goto("https://pe.indeed.com/cmp/Despegar.com", timeout=60000)
    time.sleep(3)

    if has_turnstile(page):
        print("    Turnstile...")
        bypass_turnstile(page)
        time.sleep(3)

    print(f"    URL: {page.url}")
    print(f"    Title: {page.title()}")

    # Зберігаємо
    page.screenshot(path="debug_results/despegar.png")
    with open("debug_results/despegar.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("    Збережено: debug_results/despegar.png та .html")

    # Шукаємо сайт - всі можливі селектори
    print("\n[2] Пошук посилання на сайт...")

    selectors = [
        'li[data-testid="companyInfo-companyWebsite"] a',
        '[data-testid="companyInfo-companyWebsite"]',
        '[data-testid*="Website"]',
        'a[data-tn-element="companyWebsite"]',
        'a[href*="despegar.com"]',
        '.css-1lhpb9z a',
    ]

    for sel in selectors:
        elem = page.query_selector(sel)
        if elem:
            href = elem.get_attribute("href")
            text = elem.inner_text()
            print(f"    ✓ {sel}")
            print(f"      href: {href}")
            print(f"      text: {text}")
        else:
            print(f"    ✗ {sel}")

    # Всі посилання на сторінці
    print("\n[3] Всі зовнішні посилання:")
    for link in page.query_selector_all("a[href^='http']"):
        href = link.get_attribute("href") or ""
        text = link.inner_text().strip()[:30]
        if "indeed" not in href.lower():
            print(f"    {href[:60]} | {text}")

    # Перевіримо текст сторінки
    print("\n[4] Пошук 'sitio web' або 'website' в тексті...")
    body_text = page.inner_text("body").lower()
    if "sitio web" in body_text:
        print("    Знайдено 'sitio web' в тексті!")
        # Знайдемо контекст
        idx = body_text.find("sitio web")
        print(f"    Контекст: ...{body_text[max(0,idx-50):idx+100]}...")
    if "website" in body_text:
        print("    Знайдено 'website' в тексті!")
    if "despegar.com" in body_text:
        print("    Знайдено 'despegar.com' в тексті!")

    # Спробуємо вкладку "Acerca de"
    print("\n[5] Пошук вкладки 'Acerca de'...")
    about_tab = page.query_selector("a:has-text('Acerca de'), button:has-text('Acerca de')")
    if about_tab:
        print("    Знайдено вкладку, клікаю...")
        about_tab.click()
        time.sleep(2)

        # Зберігаємо після кліку
        page.screenshot(path="debug_results/despegar_about.png")
        with open("debug_results/despegar_about.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("    Збережено: debug_results/despegar_about.png")

        # Шукаємо сайт знову
        print("\n    Пошук сайту після переходу на 'Acerca de':")
        for sel in selectors:
            elem = page.query_selector(sel)
            if elem:
                href = elem.get_attribute("href")
                print(f"    ✓ {sel}: {href}")

        # Всі зовнішні посилання
        print("\n    Зовнішні посилання:")
        for link in page.query_selector_all("a[href^='http']"):
            href = link.get_attribute("href") or ""
            if "indeed" not in href.lower():
                print(f"    {href[:60]}")
    else:
        print("    Вкладка не знайдена")

    print("\n" + "="*60)
