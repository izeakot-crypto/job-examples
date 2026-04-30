"""Self-plagiarism checker — shingle-based comparison against own articles.

Compares new article against existing articles in Supabase using
Jaccard similarity of word n-grams (shingles).
"""
import re
import logging
import asyncio

from utils.html_utils import strip_html

logger = logging.getLogger(__name__)

SHINGLE_SIZE = 4  # 4-word shingles
SIMILARITY_THRESHOLD = 25  # % — above this is suspicious


def _make_shingles(text: str, n: int = SHINGLE_SIZE) -> set[str]:
    """Create a set of n-word shingles from text."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    words = clean.split()
    if len(words) < n:
        return set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) * 100


async def check_self_plagiarism(
    texts: dict[str, str],
    idea_id: str = "",
) -> dict[str, dict]:
    """Check new article texts against existing articles in DB.

    Args:
        texts: {lang: html_content} — new article texts
        idea_id: current article ID to exclude from comparison

    Returns:
        {lang: {"similarity": float, "similar_articles": list, "status": str}}
    """
    from services.supabase_client import get_client

    results = {}

    # Lang suffix mapping
    suffix_map = {"en": "en", "ru": "ru", "pl": "pl", "es": "es", "tr": "tr", "uk": "ua"}

    # Only fetch columns we actually need
    needed_columns = {f"translation_{suffix_map.get(lang, lang)}" for lang in texts}
    select_cols = "id, " + ", ".join(sorted(needed_columns))

    try:
        client = get_client()

        query = client.table("articles_audit").select(select_cols)
        if idea_id:
            query = query.neq("id", idea_id)
        response = await asyncio.to_thread(
            lambda: query.order("created_at", desc=True).limit(100).execute()
        )

        existing_articles = response.data or []

        if not existing_articles:
            for lang in texts:
                results[lang] = {"similarity": 0, "similar_articles": [], "status": "ok"}
            return results

    except Exception as e:
        logger.warning(f"[SelfPlag] DB error: {e}")
        for lang in texts:
            results[lang] = {"similarity": 0, "similar_articles": [], "status": "error"}
        return results

    for lang, content in texts.items():
        new_plain = strip_html(content)
        new_shingles = _make_shingles(new_plain)

        if not new_shingles:
            results[lang] = {"similarity": 0, "similar_articles": [], "status": "ok"}
            continue

        suffix = suffix_map.get(lang, lang)
        max_similarity = 0.0
        similar_articles = []

        for article in existing_articles:
            existing_content = article.get(f"translation_{suffix}", "")
            if not existing_content:
                continue

            existing_plain = strip_html(existing_content)
            existing_shingles = _make_shingles(existing_plain)

            sim = jaccard_similarity(new_shingles, existing_shingles)

            if sim > 5:  # Only report if >5% similar
                similar_articles.append({
                    "article_id": article["id"],
                    "similarity": round(sim, 1),
                })

            if sim > max_similarity:
                max_similarity = sim

        results[lang] = {
            "similarity": round(max_similarity, 1),
            "similar_articles": sorted(similar_articles, key=lambda x: -x["similarity"])[:3],
            "status": "fail" if max_similarity > SIMILARITY_THRESHOLD else "ok",
        }

    return results
