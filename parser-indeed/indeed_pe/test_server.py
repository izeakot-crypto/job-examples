#!/usr/bin/env python3
"""Quick server test for Peru"""

import sys, os, time, re
sys.stdout.reconfigure(encoding='utf-8')
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['GALLIUM_DRIVER'] = 'llvmpipe'

from camoufox.sync_api import Camoufox

INDEED_DOMAIN = 'pe.indeed.com'
QUERIES = ['Operador', 'teleoperador']

def has_turnstile(page):
    if 'un momento' in (page.title() or '').lower():
        return True
    for frame in page.frames:
        if 'challenges.cloudflare.com' in frame.url:
            return True
    return False

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
        if not has_turnstile(page):
            return True
    return False

print('='*60)
print('SERVER TEST: Peru Indeed (2 queries)')
print('='*60)

results = []
seen = set()

with Camoufox(headless=False, humanize=True, os='windows', locale='es-PE') as browser:
    page = browser.new_page()

    print('\n[1] Checking IP...')
    page.goto('https://api.ipify.org?format=json', timeout=30000)
    time.sleep(1)
    print(f'    {page.inner_text("body")}')

    page.goto('https://www.google.com.pe', timeout=30000)
    time.sleep(2)

    for q in QUERIES:
        print(f'\n[QUERY: {q}]')
        page.goto(f'https://{INDEED_DOMAIN}/jobs?q={q}&l=', timeout=60000)
        time.sleep(3)
        if has_turnstile(page):
            print('  Turnstile...')
            bypass_turnstile(page)
            time.sleep(3)

        jobs = []
        for link in page.query_selector_all('a.jcs-JobTitle')[:5]:
            href = link.get_attribute('href')
            if href:
                jobs.append(f'https://{INDEED_DOMAIN}' + href if href.startswith('/') else href)

        print(f'  Vacancies found: {len(jobs)}')

        for vac in jobs[:3]:
            page.goto(vac, timeout=60000)
            time.sleep(2)
            if has_turnstile(page):
                bypass_turnstile(page)
                time.sleep(2)

            company = ''
            ce = page.query_selector("div[data-testid='inlineHeader-companyName']")
            if ce:
                lk = ce.query_selector('a')
                company = (lk or ce).inner_text().strip()

            if not company or company.lower() in seen:
                continue
            seen.add(company.lower())

            website = ''
            cl = page.query_selector("div[data-testid='inlineHeader-companyName'] a")
            if cl:
                href = cl.get_attribute('href')
                if href:
                    cu = f'https://{INDEED_DOMAIN}' + href if href.startswith('/') else href
                    page.goto(cu, timeout=60000)
                    time.sleep(2)
                    if has_turnstile(page):
                        bypass_turnstile(page)
                        time.sleep(2)
                    we = page.query_selector('li[data-testid="companyInfo-companyWebsite"] a')
                    if we:
                        website = we.get_attribute('href') or ''

            status = 'OK' if website else 'no site'
            print(f'  - {company}: {status}')
            if website:
                print(f'    {website}')
            results.append({'company': company, 'website': website})

print(f'\n{"="*60}')
print(f'RESULT: {len(results)} companies')
with_site = len([r for r in results if r['website']])
print(f'With website: {with_site}')
print('='*60)
