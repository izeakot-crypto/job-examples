import re
import json
import logging

from utils.html_utils import normalize_html

logger = logging.getLogger(__name__)


def parse_article_response(raw_text: str) -> tuple[str, str, str]:
    """Parse Claude response, return (content, title, parse_method)."""
    clean_text = re.sub(r"```json\s*", "", raw_text)
    clean_text = re.sub(r"```\s*", "", clean_text).strip()

    # Method 1: direct JSON parse
    json_match = re.search(r'\{[\s\S]*"ARTICLE_HTML"[\s\S]*\}', clean_text)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if parsed.get("ARTICLE_HTML"):
                return (
                    normalize_html(parsed["ARTICLE_HTML"]),
                    parsed.get("SEO_HEADING", ""),
                    "json_direct",
                )
        except json.JSONDecodeError:
            pass

    # Method 2: regex extract
    html_match = re.search(r'"ARTICLE_HTML"\s*:\s*"([\s\S]*?)"\s*\}', clean_text)
    if html_match:
        extracted = html_match.group(1)
        extracted = extracted.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        title = ""
        title_match = re.search(r'"SEO_HEADING"\s*:\s*"([^"]+)"', clean_text)
        if title_match:
            title = title_match.group(1)
        return normalize_html(extracted), title, "regex"

    # Method 3: raw HTML
    if "<h1>" in clean_text or "<h2>" in clean_text or "<p>" in clean_text:
        content = normalize_html(clean_text)
        h1_match = re.search(r"<h1>([^<]+)</h1>", content, re.IGNORECASE)
        title = h1_match.group(1) if h1_match else ""
        return content, title, "html_direct"

    logger.warning("Failed to parse article response")
    return "", "", "none"
