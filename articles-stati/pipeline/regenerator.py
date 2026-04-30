"""WF3: Regeneration and Translation

Called by WF2 when a specific language fails verification.
Re-generates the article for that language, checks grammar, and returns.
"""
import asyncio
import logging

from config import MAX_ATTEMPTS, MIN_CONTENT_LENGTH, settings
from services.anthropic_client import generate_article
from services.grammar import (
    apply_grammar_fixes,
    check_grammar_languagetool,
    check_grammar_turkish,
)
from services.supabase_client import get_idea
from utils.html_utils import content_length_no_spaces, fix_html_structure
from utils.text_utils import parse_article_response

logger = logging.getLogger(__name__)


async def regenerate_language(
    lang: str,
    idea_id: str,
    theme: str,
    reason: str = "",
) -> dict:
    """Regenerate article for a single language.

    Returns:
        {"content": str, "title": str, "success": bool}
    """
    logger.info(f"[{lang}] Regenerating. Reason: {reason}")

    # Fetch idea for latest data
    try:
        idea = await asyncio.to_thread(get_idea, idea_id)
    except Exception as e:
        logger.error(f"[{lang}] Failed to fetch idea: {e}")
        return {"content": "", "title": "", "success": False}

    title = idea.get("title", theme)
    keywords = idea.get("keywords", "")
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)

    best_content = ""
    best_title = ""
    best_length = 0

    for attempt in range(MAX_ATTEMPTS):
        logger.info(f"[{lang}] Regen attempt {attempt + 1}/{MAX_ATTEMPTS}")

        # Generate with failure reason so Claude knows what to fix
        try:
            raw_response = await generate_article(lang, title, keywords, regen_reason=reason)
        except Exception as e:
            logger.error(f"[{lang}] Claude failed: {e}")
            continue

        # Parse
        content, article_title, _ = parse_article_response(raw_response)
        if not content:
            continue

        # Grammar check
        if lang == "tr":
            tr_result = await check_grammar_turkish(content, settings.browser_ws_primary)
            corrected = tr_result if isinstance(tr_result, str) and tr_result else content
        else:
            matches = await check_grammar_languagetool(content, lang)
            corrected, _, _ = apply_grammar_fixes(content, matches)

        # Fix HTML structure (extra h1 -> h2, unclosed tags)
        corrected = fix_html_structure(corrected)

        length = content_length_no_spaces(corrected)

        # Keep the best result
        if length > best_length:
            best_content = corrected
            best_title = article_title or title
            best_length = length

        if length >= MIN_CONTENT_LENGTH:
            logger.info(f"[{lang}] Regen OK — {length} chars")
            return {"content": corrected, "title": article_title or title, "success": True}

        logger.warning(f"[{lang}] Regen too short: {length} chars")

    # Return best attempt even if short
    logger.warning(f"[{lang}] Max regen attempts reached, returning best: {best_length} chars")
    return {"content": best_content, "title": best_title, "success": best_length > 0}
