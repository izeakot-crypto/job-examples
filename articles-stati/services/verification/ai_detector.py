"""AI detection service — uses Claude proxy to evaluate text naturalness.

Replaces ZeroGPT and Copyleaks. Free, reliable, no browser automation.
"""
import json
import re
import logging

from services.anthropic_client import get_client

logger = logging.getLogger(__name__)

USER_PROMPT_TEMPLATE = (
    "You are an AI text detection expert. Analyze the text below and estimate "
    "the probability (0-100) it was written by AI.\n\n"
    "Consider: sentence structure variety, word choice patterns, "
    "transition phrases overuse, paragraph regularity, specificity, repetition.\n\n"
    "IMPORTANT: Your entire response must be ONLY this JSON, nothing else:\n"
    '{{"ai_probability": <0-100>, "confidence": "<low|medium|high>", '
    '"signals": ["<signal1>", "<signal2>"]}}\n\n'
    "TEXT ({lang}):\n{text}"
)


def _parse_ai_response(raw: str) -> dict:
    """Extract AI detection result from response, handling non-JSON responses."""
    # Try direct JSON parse
    try:
        # Strip markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        result = json.loads(cleaned)
        return {
            "ai_probability": float(result.get("ai_probability", 50)),
            "confidence": result.get("confidence", "medium"),
            "signals": result.get("signals", []),
        }
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON object in text
    json_match = re.search(r'\{[^{}]*"ai_probability"\s*:\s*\d+[^{}]*\}', raw)
    if json_match:
        try:
            result = json.loads(json_match.group())
            return {
                "ai_probability": float(result.get("ai_probability", 50)),
                "confidence": result.get("confidence", "medium"),
                "signals": result.get("signals", []),
            }
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: extract probability from text patterns
    prob_patterns = [
        r"(\d{1,3})\s*%\s*(?:probability|likely|chance|AI)",
        r"(?:probability|likely|chance|AI)\s*[:\-=]\s*(\d{1,3})\s*%",
        r"(\d{1,3})\s*%",
    ]
    for pattern in prob_patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            prob = float(match.group(1))
            if 0 <= prob <= 100:
                confidence = "low" if prob < 40 else "medium" if prob < 70 else "high"
                return {
                    "ai_probability": prob,
                    "confidence": confidence,
                    "signals": ["parsed from text response"],
                }

    logger.warning(f"[AI Detector] Could not parse response: {raw[:200]}")
    return {"ai_probability": 50, "confidence": "low", "signals": ["unparseable response"]}


def _sample_text(text: str, max_chars: int = 4000) -> str:
    """Sample text from beginning, middle, and end for better coverage."""
    if len(text) <= max_chars:
        return text

    chunk = max_chars // 3
    beginning = text[:chunk]
    middle_start = (len(text) - chunk) // 2
    middle = text[middle_start:middle_start + chunk]
    end = text[-chunk:]
    return f"{beginning}\n[...]\n{middle}\n[...]\n{end}"


async def detect_ai_single(text: str, lang: str) -> dict:
    """Detect AI probability for a single text.

    Returns:
        {"ai_probability": float, "confidence": str, "signals": list}
    """
    sample = _sample_text(text)

    try:
        client = get_client()
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(lang=lang.upper(), text=sample),
            }],
        )

        raw = response.content[0].text.strip()
        return _parse_ai_response(raw)

    except Exception as e:
        logger.error(f"[AI Detector] Error for {lang}: {e}")
        return {"ai_probability": 50, "confidence": "low", "signals": [f"error: {str(e)}"]}


async def check_ai_detection(texts: dict[str, str]) -> dict[str, dict]:
    """Check AI detection for multiple languages.

    Runs sequentially to avoid overwhelming the Claude proxy.

    Args:
        texts: {lang: plain_text}

    Returns:
        {lang: {"ai_probability": float, "confidence": str, "signals": list}}
    """
    import asyncio
    results = {}

    # Run sequentially — proxy may have rate limits
    for lang, text in texts.items():
        results[lang] = await detect_ai_single(text, lang)
        # Small delay between requests
        if len(texts) > 1:
            await asyncio.sleep(1)

    return results
