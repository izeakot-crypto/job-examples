"""Text statistics service — replaces Advego.

Calculates water %, academic nausea, classic nausea locally.
No external services, instant results.
"""
import math
import re
import logging
from collections import Counter

from utils.html_utils import strip_html
from services.verification.stop_words import STOP_WORDS

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase words, removing punctuation."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in clean.split() if len(w) > 1]


def _count_sentences(text: str) -> int:
    """Count sentences by splitting on sentence-ending punctuation."""
    sentences = re.split(r"[.!?]+", text)
    return len([s for s in sentences if s.strip()])


def analyze_text(html_content: str, lang: str) -> dict:
    """Analyze text and return statistics.

    Args:
        html_content: HTML article content
        lang: Language code (en/ru/pl/es/tr/uk)

    Returns:
        {
            "water": float,              # Water % (stop words ratio)
            "academic_nausea": float,     # Academic nausea %
            "classic_nausea": float,      # Classic nausea (sqrt)
            "word_count": int,
            "char_count": int,
            "char_count_no_spaces": int,
            "sentence_count": int,
            "avg_sentence_length": float,
            "top_words": list,            # Top 10 most frequent words
            "status": str,               # "ok" or "error"
        }
    """
    try:
        plain = strip_html(html_content)
        if not plain or len(plain.strip()) < 50:
            return {"water": 0, "academic_nausea": 0, "classic_nausea": 0,
                    "word_count": 0, "status": "error"}

        words = _tokenize(plain)
        total_words = len(words)

        if total_words == 0:
            return {"water": 0, "academic_nausea": 0, "classic_nausea": 0,
                    "word_count": 0, "status": "error"}

        # Stop words for this language
        stop_set = STOP_WORDS.get(lang, STOP_WORDS.get("en", set()))
        stop_count = sum(1 for w in words if w in stop_set)

        # Water %
        water = round(stop_count / total_words * 100, 1)

        # Word frequency
        freq = Counter(words)
        # Exclude stop words from nausea calculation
        content_freq = Counter({w: c for w, c in freq.items() if w not in stop_set and len(w) > 2})

        if content_freq:
            most_common_word, most_common_count = content_freq.most_common(1)[0]
        else:
            most_common_word, most_common_count = "", 0

        # Academic nausea = max_word_freq / total_words * 100
        academic_nausea = round(most_common_count / total_words * 100, 1) if total_words > 0 else 0

        # Classic nausea = sqrt(max_word_count)
        classic_nausea = round(math.sqrt(most_common_count), 2) if most_common_count > 0 else 0

        # Sentence stats
        sentence_count = _count_sentences(plain)
        avg_sentence_len = round(total_words / sentence_count, 1) if sentence_count > 0 else 0

        # Top 10 content words
        top_words = [
            {"word": w, "count": c, "pct": round(c / total_words * 100, 1)}
            for w, c in content_freq.most_common(10)
        ]

        return {
            "water": water,
            "academic_nausea": academic_nausea,
            "classic_nausea": classic_nausea,
            "word_count": total_words,
            "char_count": len(plain),
            "char_count_no_spaces": len(plain.replace(" ", "")),
            "sentence_count": sentence_count,
            "avg_sentence_length": avg_sentence_len,
            "top_words": top_words,
            "most_frequent_word": most_common_word,
            "status": "ok",
        }

    except Exception as e:
        logger.error(f"[TextStats] Error analyzing {lang}: {e}")
        return {"water": 0, "academic_nausea": 0, "classic_nausea": 0,
                "word_count": 0, "status": "error"}


def check_text_stats(texts: dict[str, str]) -> dict[str, dict]:
    """Check text stats for multiple languages.

    Args:
        texts: {lang: html_content}

    Returns:
        {lang: stats_dict}
    """
    results = {}
    for lang, content in texts.items():
        results[lang] = analyze_text(content, lang)
    return results
