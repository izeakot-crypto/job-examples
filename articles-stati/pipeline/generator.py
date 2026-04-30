"""WF1: Article Generation & Translation

Triggered when frontend approves an article idea.
Generates articles in 6 languages via Claude, checks grammar, retries if too short.
Then fires WF2 (Article Verification) asynchronously.
"""
import asyncio
import logging
from dataclasses import dataclass

from config import LANGUAGES, MAX_ATTEMPTS, MIN_CONTENT_LENGTH, settings
from services.anthropic_client import generate_article
from services.grammar import (
    apply_grammar_fixes,
    check_grammar_languagetool,
    check_grammar_turkish,
)
from services.progress import notify_progress
from services.supabase_client import get_idea
from utils.html_utils import content_length_no_spaces, content_length_with_spaces, fix_html_structure
from utils.text_utils import parse_article_response

logger = logging.getLogger(__name__)


@dataclass
class ArticleResult:
    lang: str
    content: str = ""
    title: str = ""
    content_length: int = 0
    content_length_no_spaces: int = 0
    parse_method: str = "none"
    length_status: str = "UNKNOWN"
    grammar_fixed: int = 0
    grammar_skipped: int = 0
    attempts: int = 0
    success: bool = False


async def _process_language(lang: str, idea: dict) -> ArticleResult:
    """Generate, grammar-check, and fix an article for one language. Retries up to MAX_ATTEMPTS."""
    title = idea.get("title", "")
    keywords = idea.get("keywords", "")
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)

    result = ArticleResult(lang=lang)

    for attempt in range(MAX_ATTEMPTS):
        result.attempts = attempt + 1
        logger.info(f"[{lang}] Attempt {attempt + 1}/{MAX_ATTEMPTS}")

        # 1. Generate article via Claude
        try:
            raw_response = await generate_article(lang, title, keywords)
        except Exception as e:
            logger.error(f"[{lang}] Claude generation failed: {e}")
            continue

        # 2. Parse response
        content, article_title, parse_method = parse_article_response(raw_response)
        if not content:
            logger.warning(f"[{lang}] Empty content after parsing")
            continue

        result.title = article_title or title
        result.parse_method = parse_method

        # 3. Grammar check
        if lang == "tr":
            grammar_result = await check_grammar_turkish(content, settings.browser_ws_primary)
            # Turkish grammar returns a dict, not LanguageTool matches — skip apply_fixes
            result.content = content
        else:
            matches = await check_grammar_languagetool(content, lang)
            corrected, fixed, skipped = apply_grammar_fixes(content, matches)
            result.content = corrected
            result.grammar_fixed = fixed
            result.grammar_skipped = skipped

        # 4. Fix HTML structure (extra h1 -> h2, unclosed tags)
        result.content = fix_html_structure(result.content)

        # 5. Check length
        result.content_length_no_spaces = content_length_no_spaces(result.content)
        result.content_length = content_length_with_spaces(result.content)

        ln = result.content_length_no_spaces
        if ln == 0:
            result.length_status = "EMPTY"
        elif ln < 5000:
            result.length_status = "VERY_SHORT"
        elif ln < MIN_CONTENT_LENGTH:
            result.length_status = "TOO_SHORT"
        elif ln <= 18000:
            result.length_status = "OK"
        else:
            result.length_status = "TOO_LONG"

        # 5. Check if good enough (n8n checks content_length WITH spaces)
        if result.content_length >= MIN_CONTENT_LENGTH:
            result.success = True
            logger.info(f"[{lang}] OK — {result.content_length_no_spaces} chars")
            break
        else:
            logger.warning(
                f"[{lang}] Too short: {result.content_length_no_spaces} chars, retrying..."
            )

    # If max attempts reached, accept whatever we have
    if not result.success and result.content:
        result.success = True
        logger.warning(f"[{lang}] Max attempts reached, accepting {result.content_length_no_spaces} chars")

    return result


def _build_save_payload(idea: dict, results: dict[str, ArticleResult]) -> dict:
    """Build the payload to pass to Article Verification (WF2)."""
    payload = {
        "idea_id": idea.get("id"),
        "description": idea.get("description", ""),
        "keywords": idea.get("keywords", []),
        "created_at": idea.get("created_at"),
        "updated_at": idea.get("updated_at"),
        "theme": "",
    }

    lang_map = {"en": "en", "ru": "ru", "pl": "pl", "es": "es", "tr": "tr", "uk": "ua"}

    for lang, r in results.items():
        suffix = lang_map[lang]
        payload[f"translation_{suffix}"] = r.content
        payload[f"theme_{suffix}"] = r.title

    # Set main theme from Ukrainian
    uk_result = results.get("uk")
    if uk_result and uk_result.title:
        payload["theme"] = uk_result.title
    else:
        first_with_title = next((r for r in results.values() if r.title), None)
        payload["theme"] = first_with_title.title if first_with_title else "Untitled"

    return payload


async def run_generation(idea_id: str) -> dict:
    """Main entry point for WF1. Returns payload for WF2."""
    # Notify frontend
    await notify_progress(idea_id, "generating", 30, "Стаття генерується...")

    # Fetch idea from Supabase
    idea = await asyncio.to_thread(get_idea, idea_id)
    logger.info(f"Generating articles for idea: {idea.get('title', 'unknown')}")

    # Run languages sequentially — Claude proxy has concurrency limit
    results: dict[str, ArticleResult] = {}
    for i, lang in enumerate(LANGUAGES):
        try:
            results[lang] = await _process_language(lang, idea)
        except Exception as e:
            logger.error(f"[{lang}] Pipeline failed: {e}")
            results[lang] = ArticleResult(lang=lang)
        # Delay between languages to avoid proxy rate limits
        if i < len(LANGUAGES) - 1:
            await asyncio.sleep(3)

    # Build payload for verification
    payload = _build_save_payload(idea, results)

    logger.info(
        f"Generation complete. Languages: "
        f"{[f'{l}:{r.content_length_no_spaces}' for l, r in results.items()]}"
    )
    return payload
