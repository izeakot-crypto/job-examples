import html as html_module
import re


def normalize_html(html: str) -> str:
    if not html:
        return ""
    cleaned = html
    cleaned = re.sub(r"<!--[\s\S]*?-->", "", cleaned)
    cleaned = re.sub(r'\s*(style|class|id)\s*=\s*["\'][^"\']*["\']', "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\/?(div|span|article|section|br)[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<p>\s*</p>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def strip_html(html_content: str) -> str:
    if not html_content:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Decode all HTML entities (named, numeric, hex)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fix_html_structure(html: str) -> str:
    """Fix common HTML issues in generated articles."""
    if not html:
        return ""

    result = html

    # 1. Keep only the first <h1>, convert extra <h1> to <h2>
    h1_matches = list(re.finditer(r"<h1([^>]*)>(.*?)</h1>", result, re.IGNORECASE | re.DOTALL))
    if len(h1_matches) > 1:
        for match in h1_matches[1:]:
            result = result.replace(match.group(0), f"<h2{match.group(1)}>{match.group(2)}</h2>")

    # 2. Fix unclosed <p> tags — find <p> not followed by </p> before next block tag
    # Simple approach: ensure every <p> has a matching </p>
    block_tags = r"<(?:h[1-6]|p|ul|ol|li|table|blockquote)[>\s/]"
    fixed_parts = []
    p_open = False
    i = 0
    while i < len(result):
        # Check for opening <p>
        p_open_match = re.match(r"<p(\s[^>]*)?>", result[i:], re.IGNORECASE)
        if p_open_match:
            if p_open:
                fixed_parts.append("</p>")
            fixed_parts.append(p_open_match.group(0))
            p_open = True
            i += len(p_open_match.group(0))
            continue

        # Check for closing </p>
        p_close_match = re.match(r"</p>", result[i:], re.IGNORECASE)
        if p_close_match:
            fixed_parts.append("</p>")
            p_open = False
            i += len(p_close_match.group(0))
            continue

        # Check for other block-level opening tags while <p> is open
        if p_open:
            block_match = re.match(block_tags, result[i:], re.IGNORECASE)
            if block_match and not result[i:].startswith("<p"):
                fixed_parts.append("</p>")
                p_open = False

        fixed_parts.append(result[i])
        i += 1

    if p_open:
        fixed_parts.append("</p>")
    result = "".join(fixed_parts)

    return result


def content_length_no_spaces(html: str) -> int:
    if not html:
        return 0
    clean = re.sub(r"<[^>]+>", "", html)
    clean = re.sub(r"&[a-z]+;", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", "", clean)
    return len(clean)


def content_length_with_spaces(html: str) -> int:
    if not html:
        return 0
    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"&[a-z]+;", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return len(clean)
