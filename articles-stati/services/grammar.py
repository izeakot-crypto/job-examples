import re
import logging

import httpx

from config import (
    LANGUAGETOOL_URL, LANG_TO_LANGUAGETOOL,
    GRAMMAR_MAX_CHARS, PROTECTED_TERMS,
)
from utils.html_utils import strip_html

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30)
    return _http_client


async def check_grammar_languagetool(content: str, lang: str) -> list[dict]:
    """Check grammar via LanguageTool API. Returns list of matches."""
    lt_lang = LANG_TO_LANGUAGETOOL.get(lang)
    if not lt_lang:
        return []

    plain = strip_html(content)[:GRAMMAR_MAX_CHARS]
    if not plain:
        return []

    try:
        client = await _get_http_client()
        resp = await client.post(
            LANGUAGETOOL_URL,
            data={"text": plain, "language": lt_lang},
        )
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except Exception as e:
        logger.warning(f"Grammar check failed for {lang}: {e}")
        return []


async def check_grammar_turkish(content: str, browser_ws: str) -> dict:
    """Check Turkish grammar via Playwright on paraphrasetool.com."""
    from playwright.async_api import async_playwright

    plain = strip_html(content)[:5000]
    if len(plain) < 100:
        return {"errors": 0, "status": "skipped", "list": []}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(browser_ws)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(
                "https://paraphrasetool.com/langs/turkish-grammar-checker",
                wait_until="networkidle",
                timeout=90000,
            )
            await page.wait_for_timeout(5000)

            textarea = page.locator("textarea").first
            await textarea.fill(plain)
            await page.wait_for_timeout(2000)

            check_btn = page.locator("button").filter(has_text=re.compile(r"check", re.IGNORECASE)).first
            await check_btn.click()
            await page.wait_for_timeout(15000)

            body_text = await page.locator("body").inner_text()
            lower_text = body_text.lower()

            no_error_phrases = ["no error", "no mistake", "0 error", "looks good", "correct"]
            for phrase in no_error_phrases:
                if phrase in lower_text and "incorrect" not in lower_text:
                    await browser.close()
                    return {"errors": 0, "status": "pass", "list": []}

            errors = 0
            for pattern in [r"(\d+)\s*(?:grammar\s*)?error", r"(\d+)\s*mistake", r"(\d+)\s*issue"]:
                m = re.search(pattern, body_text, re.IGNORECASE)
                if m and int(m.group(1)) > 0:
                    errors = int(m.group(1))
                    break

            status = "pass" if errors == 0 else ("warning" if errors < 5 else "fail")
            await browser.close()
            return {"errors": errors, "status": status, "list": []}

    except Exception as e:
        logger.warning(f"Turkish grammar check failed: {e}")
        return {"errors": -1, "status": "error", "message": str(e)}


def apply_grammar_fixes(content: str, matches: list[dict]) -> tuple[str, int, int]:
    """Apply LanguageTool fixes. Returns (corrected_content, fixed_count, skipped_count).

    Note: LanguageTool offsets are for plain text, but we apply fixes to HTML content.
    We use text matching (not offset-based) to find and replace the wrong text safely.
    """
    corrected = content
    fixed = 0
    skipped = 0

    for match in matches:
        replacements = match.get("replacements", [])
        context = match.get("context", {})
        if not replacements or not context:
            continue

        offset = context.get("offset", 0)
        length = context.get("length", 0)
        wrong_text = context.get("text", "")[offset:offset + length]
        replacement = replacements[0].get("value", "")

        if not wrong_text or not replacement or wrong_text == replacement:
            continue

        # Skip protected terms
        if any(t in wrong_text.lower() for t in PROTECTED_TERMS):
            skipped += 1
            continue

        # Skip if the wrong_text only appears inside HTML tags
        # Find the first occurrence in the content
        pos = corrected.find(wrong_text)
        if pos == -1:
            skipped += 1
            continue

        before = corrected[:pos]
        if before.count("<") > before.count(">"):
            skipped += 1
            continue

        escaped = re.escape(wrong_text)
        new_content = re.sub(escaped, replacement, corrected, count=1)
        if new_content != corrected:
            corrected = new_content
            fixed += 1

    return corrected, fixed, skipped
