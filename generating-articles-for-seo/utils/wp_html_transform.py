"""Transform pipeline HTML to WordPress TinyMCE-style HTML.

Pipeline uses clean semantic tags (<p>, <strong>, <h2>).
WordPress/TinyMCE uses inline styles (<span style="font-weight: 400;">, <b>).
"""
import re
from urllib.parse import quote


def _slugify(text: str) -> str:
    """Create an anchor slug from heading text."""
    slug = re.sub(r"<[^>]+>", "", text)
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return quote(slug, safe="-")


def _transform_inline(html: str) -> str:
    """Transform inline content: <strong> -> <b>, plain text -> <span style="font-weight: 400;">."""
    parts = re.split(r"(<strong[^>]*>.*?</strong>)", html, flags=re.DOTALL)
    result = []
    for part in parts:
        strong_match = re.match(r"<strong[^>]*>(.*?)</strong>", part, re.DOTALL)
        if strong_match:
            result.append(f"<b>{strong_match.group(1)}</b>")
        elif part.strip():
            result.append(f'<span style="font-weight: 400;">{part}</span>')
        elif part:
            result.append(part)
    return "".join(result)


def transform_for_wordpress(html: str) -> str:
    """Transform pipeline HTML to WordPress TinyMCE style."""
    if not html:
        return ""

    result = html

    # 1. Remove <h1> tags entirely (WP uses post title)
    result = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", result, flags=re.DOTALL)

    # 2. Transform <h2> — wrap content in span + add anchor
    def _replace_h2(m):
        content = m.group(1)
        # Strip any existing inner tags for slug, but keep them in output
        slug = _slugify(content)
        return f'<h2><span style="font-weight: 400;">{content}</span><a name="{slug}"></a></h2>'

    result = re.sub(r"<h2[^>]*>(.*?)</h2>", _replace_h2, result, flags=re.DOTALL)

    # 3. Transform <h3> — strip inline styles, wrap content in span
    def _replace_h3(m):
        content = m.group(1)
        return f'<h3><span style="font-weight: 400;">{content}</span></h3>'

    result = re.sub(r"<h3[^>]*>(.*?)</h3>", _replace_h3, result, flags=re.DOTALL)

    # 4. Transform <li> — add style and wrap inline content
    def _replace_li(m):
        inner = _transform_inline(m.group(1))
        return f'<li style="font-weight: 400;" aria-level="1">{inner}</li>'

    result = re.sub(r"<li[^>]*>(.*?)</li>", _replace_li, result, flags=re.DOTALL)

    # 5. Transform <p> — unwrap and convert content to spans/b, add line breaks between paragraphs
    def _replace_p(m):
        inner = _transform_inline(m.group(1))
        return inner + "\n\n"

    result = re.sub(r"<p[^>]*>(.*?)</p>", _replace_p, result, flags=re.DOTALL)

    # 6. Any remaining standalone <strong> outside of <p>/<li> -> <b>
    result = re.sub(r"<strong[^>]*>(.*?)</strong>", r"<b>\1</b>", result, flags=re.DOTALL)

    # 7. Clean up excessive blank lines (3+ newlines -> 2)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
