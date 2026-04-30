"""Google uniqueness checker — spot-check sentences via Google Custom Search API.

Extracts random sentences from article, searches Google, checks for exact matches.
Free tier: 100 queries/day.
"""
import asyncio
import random
import re
import logging

import httpx

from config import settings
from utils.html_utils import strip_html

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
SENTENCES_TO_CHECK = 5
MIN_SENTENCE_LENGTH = 40  # chars — skip short sentences


def _extract_sentences(text: str) -> list[str]:
    """Extract meaningful sentences from plain text."""
    sentences = re.split(r"[.!?]+", text)
    return [
        s.strip()
        for s in sentences
        if len(s.strip()) >= MIN_SENTENCE_LENGTH
    ]


async def check_google_uniqueness(
    texts: dict[str, str],
    sentences_per_lang: int = SENTENCES_TO_CHECK,
) -> dict[str, dict]:
    """Check text uniqueness via Google Custom Search.

    Args:
        texts: {lang: html_content}
        sentences_per_lang: number of sentences to check per language

    Returns:
        {lang: {"uniqueness": float, "matches": list, "checked": int, "status": str}}
    """
    # Check if Google API is configured
    if not settings.google_cse_key or not settings.google_cse_id:
        logger.warning("[Google] API key or CSE ID not configured, skipping")
        return {
            lang: {"uniqueness": 100, "matches": [], "checked": 0, "status": "skipped"}
            for lang in texts
        }

    results = {}

    async with httpx.AsyncClient(timeout=15) as client:
        for lang, content in texts.items():
            plain = strip_html(content)
            sentences = _extract_sentences(plain)

            if not sentences:
                results[lang] = {"uniqueness": 100, "matches": [], "checked": 0, "status": "ok"}
                continue

            # Pick random sentences
            sample = random.sample(sentences, min(sentences_per_lang, len(sentences)))

            matches = []
            checked = 0

            for sentence in sample:
                # Use exact phrase search (quotes)
                query = f'"{sentence[:100]}"'  # Limit query length

                try:
                    resp = await client.get(
                        GOOGLE_SEARCH_URL,
                        params={
                            "key": settings.google_cse_key,
                            "cx": settings.google_cse_id,
                            "q": query,
                            "num": 3,
                        },
                    )
                    checked += 1

                    if resp.status_code == 200:
                        data = resp.json()
                        total_results = int(data.get("searchInformation", {}).get("totalResults", "0"))

                        if total_results > 0:
                            items = data.get("items", [])
                            matches.append({
                                "sentence": sentence[:80] + "...",
                                "found_in": [
                                    {"title": item.get("title", ""), "url": item.get("link", "")}
                                    for item in items[:2]
                                ],
                            })
                    elif resp.status_code == 429:
                        logger.warning("[Google] Rate limit reached, stopping")
                        break

                except Exception as e:
                    logger.warning(f"[Google] Search error: {e}")

            # Delay between languages to avoid rate limits
            await asyncio.sleep(1)

            # Uniqueness = % of sentences NOT found
            uniqueness = round((1 - len(matches) / checked) * 100, 1) if checked > 0 else 100

            results[lang] = {
                "uniqueness": uniqueness,
                "matches": matches,
                "checked": checked,
                "status": "ok" if uniqueness >= 80 else "warning" if uniqueness >= 60 else "fail",
            }

    return results
