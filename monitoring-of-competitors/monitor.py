#!/usr/bin/env python3
"""
Competitor Monitoring System for Oki-toki
Replaces n8n workflow with full Python implementation.
Collects data from websites, YouTube, G2, social media,
analyzes with Claude AI, and writes results to Google Sheets.
"""

import json
import os
import re
import sys
import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GOOGLE_SA_FILE = os.getenv(
    "GOOGLE_SA_FILE",
    r"[USER_HOME]\Downloads\noted-creek-481412-k7-4747914a19d4.json",
)
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID", "YOUR_SECRET_TOKEN"
)
SHEET_NAME = os.getenv("SHEET_NAME", "Competitor_Analysis_Template")
COMPANIES_SPREADSHEET_ID = os.getenv(
    "COMPANIES_SPREADSHEET_ID", "YOUR_SECRET_TOKEN"
)
COMPANIES_JSON = os.path.join(os.path.dirname(__file__), "config", "companies.json")

# Claude model — cheap & fast, enough for structured extraction
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 2500

# Limits to keep token usage low
MAX_PAGE_TEXT_CHARS = 1500  # per page
MAX_PAGES_PER_CATEGORY = 3
MAX_TOTAL_CONTENT_CHARS = 6000  # total content sent to Claude

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("monitor")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_get(url: str, timeout: int = 30) -> requests.Response | None:
    """GET with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp
    except Exception as e:
        log.warning("  Failed to fetch %s: %s", url, e)
        return None


def clean_html_text(html: str, max_chars: int = 3000) -> str:
    """Extract clean text from HTML, removing nav/footer/scripts."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def extract_company_name(url: str) -> str:
    """Extract company name from URL."""
    m = re.match(r"https?://(?:www\.)?([^/.]+)", url)
    return m.group(1).capitalize() if m else "Unknown"


# ---------------------------------------------------------------------------
# 1. Website crawler — replaces "website checker_backup" sub-workflow
# ---------------------------------------------------------------------------
def _fetch_sitemap_urls(sitemap_url: str, domain: str, depth: int = 0) -> set[str]:
    """Recursively fetch URLs from a sitemap (handles sitemap index)."""
    if depth > 2:
        return set()
    resp = safe_get(sitemap_url, timeout=10)
    if not resp or resp.status_code != 200:
        return set()
    text = resp.text
    # Extract <loc> values, stripping CDATA wrappers if present
    raw_locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.IGNORECASE)
    locs = []
    for loc in raw_locs:
        loc = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", loc).strip()
        if loc:
            locs.append(loc)
    if not locs:
        return set()

    # Check if it's a sitemap index (contains links to other sitemaps)
    if "<sitemapindex" in text.lower():
        urls = set()
        for child_url in locs[:5]:  # limit child sitemaps
            urls |= _fetch_sitemap_urls(child_url.strip(), domain, depth + 1)
        return urls

    # Regular sitemap — return page URLs
    return {loc.strip() for loc in locs if loc.strip().startswith("http") and domain in loc}


def discover_urls(base_url: str) -> list[dict]:
    """
    Discover internal URLs via robots.txt, sitemaps, and homepage crawl.
    Replaces the 'website checker_backup' n8n sub-workflow.
    Returns list of {url, category}.
    """
    parsed = urlparse(base_url)
    domain = parsed.netloc
    root = f"{parsed.scheme}://{domain}"
    urls_found: set[str] = set()

    # Step 1: Check robots.txt for sitemap locations
    sitemap_candidates = []
    resp = safe_get(root + "/robots.txt", timeout=5)
    if resp and resp.status_code == 200:
        for m in re.finditer(r"Sitemap:\s*(.+)", resp.text, re.IGNORECASE):
            sitemap_candidates.append(m.group(1).strip())

    # Step 2: Add standard sitemap paths
    for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
                 "/sitemap/sitemap.xml", "/wp-sitemap.xml"]:
        sitemap_candidates.append(root + path)

    # Deduplicate
    seen = set()
    unique_sitemaps = []
    for s in sitemap_candidates:
        if s not in seen:
            seen.add(s)
            unique_sitemaps.append(s)

    # Step 3: Try each sitemap
    for sitemap_url in unique_sitemaps:
        found = _fetch_sitemap_urls(sitemap_url, domain)
        if found:
            urls_found |= found
            log.info("  Sitemap %s: found %d URLs", sitemap_url.split("/")[-1], len(found))
            break  # one successful sitemap is enough

    # Step 4: Fallback — crawl homepage for internal links
    if len(urls_found) < 5:
        resp = safe_get(base_url, timeout=20)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full = urljoin(base_url, href)
                if domain in full and full.startswith("http"):
                    urls_found.add(full.split("#")[0].split("?")[0])
        log.info("  Homepage crawl: found %d URLs", len(urls_found))

    log.info("  Total discovered URLs: %d", len(urls_found))
    return categorize_urls(list(urls_found), base_url)


CATEGORY_PATTERNS = {
    "blog": re.compile(
        r"/(blog|blogs|article|articles|post|posts|insights|journal|"
        r"resources|knowledge|library|learn|guides?|hub|content|"
        r"webinars?|ebook|whitepaper|academy|tutorials?|tips|recursos|"
        r"novosti|stati|publikacii)", re.I
    ),
    "news": re.compile(
        r"/(news|press|announcements|newsroom|events|updates|releases|"
        r"changelog|whats-new|novedades|actualizaciones|media|"
        r"meropriyatiya|sobytiya)", re.I
    ),
    "reviews": re.compile(
        r"/(reviews?|testimonials?|customer-stories|success-stories|"
        r"case-studies|otzyvy|klienty|clients|customers|references|"
        r"referencias)", re.I
    ),
    "pricing": re.compile(
        r"/(pricing|price|prices|plans|tarif|cost|tariffs|ceny|"
        r"stoimost|packages|subscription|tarifas|precios)", re.I
    ),
    "features": re.compile(
        r"/(features?|capabilities|vozmozhnosti|resheniya|funktsii|"
        r"marketplace|integraciya|products?|solutions?|services|"
        r"platform|why|tour|overview|what-is|funcionalidades|"
        r"soluciones|productos|tools|integrations?|modules?|api)", re.I
    ),
}


def categorize_urls(urls: list[str], base_url: str) -> list[dict]:
    """Categorize URLs into blog/news/reviews/pricing/features."""
    result = []
    seen_cats: dict[str, int] = {}
    skip_paths = {"/", "/about", "/about/", "/promo/", "/contact", "/contact/", "/login", "/signup"}

    for url in urls:
        path = urlparse(url).path.rstrip("/")
        if path in skip_paths or not path or path == "/":
            continue

        for cat, pattern in CATEGORY_PATTERNS.items():
            if pattern.search(url):
                count = seen_cats.get(cat, 0)
                if count < MAX_PAGES_PER_CATEGORY:
                    result.append({"url": url, "category": cat})
                    seen_cats[cat] = count + 1
                break

    # Ensure we have at least one features URL
    if not any(r["category"] == "features" for r in result):
        result.append({"url": base_url, "category": "features"})

    return result


# ---------------------------------------------------------------------------
# 2. Page content parser — replaces "Parse Page Content" node
# ---------------------------------------------------------------------------
def fetch_and_parse_page(url: str, category: str) -> dict | None:
    """Fetch a page and extract structured content."""
    resp = safe_get(url, timeout=30)
    if not resp or resp.status_code != 200:
        return None

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_desc = meta["content"]

    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]
    h3s = [h.get_text(strip=True) for h in soup.find_all("h3")][:10]

    content_parts = []

    if category in ("blog", "news"):
        # Extract article titles
        articles = []
        for article in soup.find_all(["article", "div"], class_=re.compile(
            r"post|entry|blog-item|news-item|article|card", re.I
        )):
            h = article.find(["h1", "h2", "h3", "h4"])
            if h:
                t = h.get_text(strip=True)
                if len(t) > 10:
                    articles.append(t)
        if not articles:
            articles = [h for h in h2s + h3s if len(h) > 10]
        content_parts.append("Articles: " + "; ".join(articles[:10]))

    elif category == "pricing":
        prices = re.findall(
            r"[\$€£]\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*(?:USD|EUR|GBP|руб|₽|/mo|/month|/user)",
            html, re.I
        )
        plans = [h for h in h2s + h3s if re.search(
            r"plan|price|tarif|пакет|стандарт|премиум|pro|enterprise|basic|starter|business",
            h, re.I
        )]
        if prices:
            content_parts.append("Prices: " + ", ".join(list(set(prices))[:15]))
        if plans:
            content_parts.append("Plans: " + "; ".join(plans[:8]))

    elif category == "features":
        features = []
        for li in soup.find_all("li"):
            t = li.get_text(strip=True)
            if 15 < len(t) < 200:
                features.append(t)
        content_parts.append("Features: " + "; ".join(features[:20]))

    elif category == "reviews":
        reviews_text = clean_html_text(html, 1500)
        content_parts.append("Reviews content: " + reviews_text)

    # Add headings as topics
    if h2s:
        content_parts.append("Topics: " + "; ".join(h2s[:8]))

    # Main text summary
    main_text = clean_html_text(html, MAX_PAGE_TEXT_CHARS)
    content_parts.append("Text: " + main_text)

    return {
        "url": url,
        "category": category,
        "title": title,
        "description": meta_desc,
        "content": "\n".join(content_parts)[:MAX_PAGE_TEXT_CHARS],
    }


# ---------------------------------------------------------------------------
# 3. YouTube — replaces YouTube detection + API nodes
# ---------------------------------------------------------------------------
YOUTUBE_PATTERNS = [
    (re.compile(r"youtube\.com/channel/([a-zA-Z0-9_-]+)", re.I), "channelId"),
    (re.compile(r"youtube\.com/@([a-zA-Z0-9_-]+)", re.I), "handle"),
    (re.compile(r"youtube\.com/c/([a-zA-Z0-9_-]+)", re.I), "customUrl"),
    (re.compile(r"youtube\.com/user/([a-zA-Z0-9_-]+)", re.I), "username"),
]
YT_EXCLUDE = {
    "watch", "embed", "playlist", "results", "feed", "gaming",
    "premium", "music", "kids", "tv", "shorts", "live", "about",
}


def detect_youtube_from_html(html: str) -> dict | None:
    """Find YouTube channel link in website HTML."""
    for pattern, match_type in YOUTUBE_PATTERNS:
        m = pattern.search(html)
        if m and m.group(1).lower() not in YT_EXCLUDE:
            return {"handle": m.group(1), "type": match_type}
    return None


def get_youtube_activity(html: str, company_name: str) -> str:
    """Get recent YouTube activity for a company."""
    if not YOUTUBE_API_KEY:
        return "-"

    yt = detect_youtube_from_html(html)
    if not yt:
        return "YouTube канал не знайдено на сайті"

    handle = yt["handle"]
    match_type = yt["type"]

    # Resolve channel ID
    channel_id = None
    if match_type == "channelId":
        channel_id = handle
    else:
        # Try to resolve via search
        params = {
            "part": "id,snippet",
            "key": YOUTUBE_API_KEY,
            "type": "channel",
            "q": company_name,
            "maxResults": 1,
        }
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params, timeout=10,
            )
            data = resp.json()
            if data.get("items"):
                channel_id = data["items"][0]["id"].get("channelId")
        except Exception:
            pass

        if not channel_id:
            # Try forUsername
            params2 = {
                "part": "id,snippet",
                "forUsername": handle,
                "key": YOUTUBE_API_KEY,
            }
            try:
                resp = requests.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params=params2, timeout=10,
                )
                data = resp.json()
                if data.get("items"):
                    channel_id = data["items"][0]["id"]
            except Exception:
                pass

    if not channel_id:
        return f"YouTube: @{handle} (канал не вдалось розпізнати)"

    # Search recent videos (last 7 days)
    week_ago = (datetime.now(tz=__import__('datetime').timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "order": "date",
        "maxResults": 5,
        "type": "video",
        "publishedAfter": week_ago,
        "key": YOUTUBE_API_KEY,
    }
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params, timeout=10,
        )
        data = resp.json()
        videos = data.get("items", [])
    except Exception:
        return f"YouTube: @{handle} (помилка API)"

    if not videos:
        return f"YouTube: @{handle} — немає нових відео за тиждень"

    titles = [v["snippet"]["title"] for v in videos[:3]]
    return (
        f"{len(videos)} нових відео за тиждень. "
        f"Останні: {'; '.join(titles)}"
    )


# ---------------------------------------------------------------------------
# 4. Social media detection — replaces "Auto-detect Social Links" node
# ---------------------------------------------------------------------------
SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"linkedin\.com/(?:company|in)/([a-zA-Z0-9_-]+)", re.I),
    "facebook": re.compile(r"facebook\.com/([a-zA-Z0-9._-]+)", re.I),
    "twitter": re.compile(r"(?:twitter|x)\.com/([a-zA-Z0-9_]+)", re.I),
    "instagram": re.compile(r"instagram\.com/([a-zA-Z0-9._]+)", re.I),
    "vk": re.compile(r"vk\.com/([a-zA-Z0-9._-]+)", re.I),
    "telegram": re.compile(r"t\.me/([a-zA-Z0-9_]+)", re.I),
    "tiktok": re.compile(r"tiktok\.com/@([a-zA-Z0-9._-]+)", re.I),
}
SOCIAL_EXCLUDE = {
    "facebook": {"sharer", "share", "dialog", "plugins", "tr"},
    "twitter": {"intent", "share", "home"},
    "linkedin": {"shareArticle", "share"},
}


def detect_social_links(html: str) -> dict[str, str | None]:
    """Detect social media links from website HTML."""
    result = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        m = pattern.search(html)
        if m:
            value = m.group(1)
            excludes = SOCIAL_EXCLUDE.get(platform, set())
            if value.lower() not in excludes:
                result[platform] = f"{platform}.com/{value}" if platform != "telegram" else f"t.me/{value}"
            else:
                result[platform] = None
        else:
            result[platform] = None
    return result


def format_social_activity(social: dict[str, str | None]) -> tuple[str, str, str, int]:
    """Format social data into linkedin/facebook/count."""
    linkedin = f"LinkedIn: {social['linkedin']}" if social.get("linkedin") else "-"
    facebook = f"Facebook: {social['facebook']}" if social.get("facebook") else "-"

    all_links = [f"{k}: {v}" for k, v in social.items() if v]
    count = len(all_links)

    return linkedin, facebook, "; ".join(all_links) if all_links else "-", count


# ---------------------------------------------------------------------------
# 5. G2 scraping — replaces "Fetch G2 Page" + "Parse G2 Data" nodes
# ---------------------------------------------------------------------------
def get_aggregator_data(company_name: str, company_url: str) -> str:
    """Get review data from Trustpilot (G2/Capterra blocked by anti-bot)."""
    parts = []

    # --- Trustpilot (works reliably, has JSON-LD structured data) ---
    domain = urlparse(company_url).netloc.replace("www.", "")
    tp_url = f"https://www.trustpilot.com/review/{domain}"
    resp = safe_get(tp_url, timeout=15)

    if resp and resp.status_code == 200 and len(resp.text) > 1000:
        html = resp.text
        # Parse JSON-LD for AggregateRating
        rating = None
        reviews_count = None

        m = re.search(r'"ratingValue"\s*:\s*"?(\d+\.?\d*)', html)
        if m:
            val = float(m.group(1))
            if 0 < val <= 5:
                rating = val

        m = re.search(r'"reviewCount"\s*:\s*"?(\d+)', html)
        if m:
            reviews_count = int(m.group(1))

        # Also try TrustScore from HTML attributes
        if not rating:
            m = re.search(r'TrustScore\s+(\d+\.?\d*)\s+out of\s+5', html, re.I)
            if m:
                rating = float(m.group(1))

        if rating:
            s = f"Trustpilot: {rating:.1f}/5"
            if reviews_count:
                s += f" ({reviews_count} відгуків)"
            parts.append(s)
        else:
            parts.append("Trustpilot: сторінка є, рейтинг не знайдено")
    else:
        # Try search
        search_resp = safe_get(
            f"https://www.trustpilot.com/search?query={requests.utils.quote(company_name)}",
            timeout=15,
        )
        if search_resp and search_resp.status_code == 200:
            m = re.search(r'TrustScore\s+(\d+\.?\d*)', search_resp.text, re.I)
            if m:
                parts.append(f"Trustpilot: {float(m.group(1)):.1f}/5 (з пошуку)")
            else:
                parts.append("Trustpilot: не знайдено")
        else:
            parts.append("Trustpilot: не знайдено")

    # --- G2 (usually blocked, but try anyway) ---
    g2_url = f"https://www.g2.com/search?query={requests.utils.quote(company_name)}"
    resp = safe_get(g2_url, timeout=10)
    if resp and resp.status_code == 200 and len(resp.text) > 1000:
        m = re.search(r'"ratingValue"\s*:\s*"?(\d+\.?\d*)', resp.text)
        if m:
            val = float(m.group(1))
            if 0 < val <= 5:
                parts.append(f"G2: {val:.1f}/5")

    return "; ".join(parts) if parts else "-"


# ---------------------------------------------------------------------------
# 6. Claude AI analysis — replaces "AI Agent" / "Message a model" node
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Ти аналітик конкурентів для SaaS-компанії Oki-toki (oki-toki.ua) — хмарний контакт-центр.

Oki-toki пропонує: хмарний контакт-центр, автодзвінки, омніканальність, CRM, звітність, оцінка якості розмов, IVR, черги, API/webhook/SIP інтеграції.

ПРАВИЛА:
1. Поверни ТІЛЬКИ valid JSON — перший символ { останній }
2. ЗАБОРОНЕНО: markdown, ```, коментарі, текст до/після JSON
3. Аналізуй ТІЛЬКИ надані дані — НЕ вигадуй
4. Якщо даних СПРАВДІ немає — пиши "-"
5. Якщо дані Є — обов'язково витягни інформацію, НЕ пиши "-"
6. МОВА: ТІЛЬКИ УКРАЇНСЬКА. Навіть якщо контент англійською чи іншою мовою — ПЕРЕКЛАДАЙ і пиши ВСЕ українською. Кожне поле, кожне слово — українською мовою. Це стосується newFeatures, problems, news, blogArticles, customerPains, customerWants, summary — ВСЕ українською."""


def build_user_prompt(company_data: dict) -> str:
    """Build compact user prompt from collected data."""
    pages = company_data.get("pages", {})

    # Build content summary — keep it compact
    content_parts = []
    for cat in ["features", "blog", "news", "pricing", "reviews"]:
        cat_pages = pages.get(cat, [])
        if cat_pages:
            texts = []
            for p in cat_pages[:MAX_PAGES_PER_CATEGORY]:
                texts.append(p.get("content", "")[:800])
            content_parts.append(f"[{cat.upper()}]\n" + "\n".join(texts))

    content_text = "\n\n".join(content_parts)[:MAX_TOTAL_CONTENT_CHARS]

    return f"""{company_data['company']} ({company_data['url']})
Регіон: {company_data.get('region', '-')}

YouTube: {company_data.get('youtube_activity', '-')}
LinkedIn: {company_data.get('linkedin_activity', '-')}
Facebook: {company_data.get('facebook_activity', '-')}
Соцмережі знайдено: {company_data.get('social_count', 0)}
{company_data.get('g2_data', '-')}

КОНТЕНТ СТОРІНОК:
{content_text}

Поверни JSON (ВСІ значення УКРАЇНСЬКОЮ, переклади назви статей/фіч/новин):
{{"company":"","url":"","newFeatures":["фічі УКРАЇНСЬКОЮ"],"problems":["проблеми УКРАЇНСЬКОЮ"],"reviewInsights":"висновок УКРАЇНСЬКОЮ","news":["новини УКРАЇНСЬКОЮ"],"blogArticles":["ПЕРЕКЛАДЕНІ назви статей УКРАЇНСЬКОЮ"],"youtubeActivity":"","facebookActivity":"","linkedinActivity":"","aggregatorMentions":"","socialMentionsCount":0,"customerPains":["болі УКРАЇНСЬКОЮ"],"customerWants":["потреби УКРАЇНСЬКОЮ"],"pricing":"тарифи/ціни з контенту УКРАЇНСЬКОЮ (конкретні цифри якщо є)","advantagesOverOkitoki":["конкретні переваги конкурента над Oki-toki УКРАЇНСЬКОЮ"],"targetAudience":"SMB/Enterprise/BPO — хто цільова аудиторія УКРАЇНСЬКОЮ","hasFreeTrial":"так/ні/не вказано — чи є безкоштовний тариф або тріал","summary":"2-3 речення УКРАЇНСЬКОЮ: що робить компанія, позиціонування vs Oki-toki"}}"""


def analyze_with_claude(company_data: dict) -> dict:
    """Send collected data to Claude for analysis. Returns parsed JSON."""
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY not set!")
        return _empty_result(company_data.get("company", "Unknown"), company_data.get("url", "-"))

    client_kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        client_kwargs["base_url"] = ANTHROPIC_BASE_URL
    client = anthropic.Anthropic(**client_kwargs)
    user_prompt = build_user_prompt(company_data)

    # Log token estimate
    prompt_chars = len(SYSTEM_PROMPT) + len(user_prompt)
    est_tokens = prompt_chars // 3  # rough estimate: 1 token ≈ 3 chars
    log.info("  Claude input ~%d chars (~%d tokens est.)", prompt_chars, est_tokens)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text
        usage = response.usage
        if usage and usage.input_tokens is not None:
            total_tokens = usage.input_tokens + usage.output_tokens
            log.info(
                "  Claude tokens: input=%d, output=%d, TOTAL=%d",
                usage.input_tokens, usage.output_tokens, total_tokens,
            )
        else:
            log.info("  Claude response received (%d chars)", len(text))

        # Parse JSON from response
        parsed = _extract_json(text)
        if parsed:
            return parsed
        else:
            log.warning("  Failed to parse Claude JSON response")
            return _empty_result(
                company_data.get("company", "Unknown"),
                company_data.get("url", "-"),
                error=f"JSON parse failed: {text[:200]}",
            )

    except Exception as e:
        log.error("  Claude API error: %s", e)
        return _empty_result(
            company_data.get("company", "Unknown"),
            company_data.get("url", "-"),
            error=str(e),
        )


def _extract_json(text: str) -> dict | None:
    """Extract JSON from Claude response text."""
    # Try 1: markdown code block
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try 2: first { to last }
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Try 3: entire text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _empty_result(company: str, url: str, error: str = "") -> dict:
    return {
        "company": company,
        "url": url,
        "newFeatures": ["-"],
        "problems": ["-"],
        "reviewInsights": "-",
        "news": ["-"],
        "blogArticles": ["-"],
        "youtubeActivity": "-",
        "facebookActivity": "-",
        "linkedinActivity": "-",
        "aggregatorMentions": "-",
        "socialMentionsCount": 0,
        "customerPains": ["-"],
        "customerWants": ["-"],
        "pricing": "-",
        "advantagesOverOkitoki": ["-"],
        "targetAudience": "-",
        "hasFreeTrial": "-",
        "summary": error or "-",
    }


# ---------------------------------------------------------------------------
# 7. Google Sheets — replaces Sheets nodes
# ---------------------------------------------------------------------------
def get_sheets_service():
    """Build Google Sheets API service."""
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SA_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_existing_rows(service) -> list[dict]:
    """Read existing rows from the sheet."""
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:V")
            .execute()
        )
        values = result.get("values", [])
        if not values:
            return []

        headers = values[0]
        rows = []
        for i, row in enumerate(values[1:], start=2):
            row_dict = {}
            for j, h in enumerate(headers):
                row_dict[h] = row[j] if j < len(row) else ""
            row_dict["_row_number"] = i
            rows.append(row_dict)
        return rows
    except Exception as e:
        log.error("Failed to read sheet: %s", e)
        return []


def format_row(ai_result: dict) -> list[str]:
    """Format AI result into a sheet row."""

    def arr_to_str(val, sep=", "):
        if not val:
            return "-"
        if isinstance(val, list):
            filtered = [str(v) for v in val if v and str(v) != "-"]
            return sep.join(filtered) if filtered else "-"
        return str(val) or "-"

    def safe(val):
        if not val:
            return "-"
        s = str(val).strip()
        return s if s else "-"

    return [
        datetime.now().strftime("%Y-%m-%d"),                          # A: Дата
        safe(ai_result.get("company")),                               # B: company
        safe(ai_result.get("url")),                                   # C: URL
        safe(ai_result.get("region")),                                # D: Регіон
        arr_to_str(ai_result.get("newFeatures")),                     # E: Нові фічі
        arr_to_str(ai_result.get("problems")),                        # F: Проблеми
        safe(ai_result.get("reviewInsights")),                        # G: Інсайти з коментарів
        arr_to_str(ai_result.get("news")),                            # H: Новини
        arr_to_str(ai_result.get("blogArticles")),                    # I: Статті в блозі
        safe(ai_result.get("youtubeActivity")),                       # J: YouTube активність
        safe(ai_result.get("facebookActivity")),                      # K: Facebook активність
        safe(ai_result.get("linkedinActivity")),                      # L: LinkedIn активність
        safe(ai_result.get("aggregatorMentions")),                    # M: Згадки на агрегаторах
        str(ai_result.get("socialMentionsCount", 0)),                 # N: Кількість згадок
        arr_to_str(ai_result.get("customerPains")),                   # O: Болі клієнтів
        arr_to_str(ai_result.get("customerWants")),                   # P: Хотілки клієнтів
        safe(ai_result.get("pricing")),                               # Q: Тарифи/Ціни
        arr_to_str(ai_result.get("advantagesOverOkitoki")),           # R: Переваги над Oki-toki
        safe(ai_result.get("targetAudience")),                        # S: Цільова аудиторія
        safe(ai_result.get("hasFreeTrial")),                          # T: Безкоштовний тріал
        safe(ai_result.get("summary")),                               # U: AI Summary
        "FALSE",                                                       # V: isNewEntry
    ]


SHEET_HEADERS = [
    "Дата", "company", "URL", "Регіон", "Нові фічі", "Проблеми",
    "Інсайти з коментарів", "Новини (з останньої перевірки)",
    "Статті в блозі (з останньої перевірки)", "YouTube активність",
    "Facebook активність", "LinkedIn активність", "Згадки на агрегаторах",
    "Кількість згадок в соцмережах", "Болі клієнтів з коментарів",
    "Хотілки клієнтів з коментарів", "Тарифи/Ціни",
    "Переваги над Oki-toki", "Цільова аудиторія",
    "Безкоштовний тріал", "AI Summary", "isNewEntry",
]


def write_to_sheet(service, ai_result: dict, existing_rows: list[dict]):
    """Write result to Google Sheets — update if exists, append if new."""
    company = str(ai_result.get("company", "")).lower().strip()
    url = str(ai_result.get("url", "")).lower().strip().rstrip("/")
    row_data = format_row(ai_result)

    # Find existing row
    found_row = None
    for row in existing_rows:
        row_company = str(row.get("company", row.get("Компанія", ""))).lower().strip()
        row_url = str(row.get("URL", "")).lower().strip().rstrip("/")

        name_match = (
            row_company and company and
            (row_company == company or company in row_company or row_company in company)
        )
        url_match = (
            row_url and url and url != "-" and row_url != "-" and
            (row_url == url or url in row_url or row_url in url)
        )
        if name_match or url_match:
            found_row = row
            break

    try:
        if found_row:
            row_num = found_row["_row_number"]
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A{row_num}:V{row_num}",
                valueInputOption="RAW",
                body={"values": [row_data]},
            ).execute()
            log.info("  Updated row %d for %s", row_num, ai_result.get("company"))
        else:
            row_data[21] = "TRUE"  # isNewEntry = TRUE for new companies
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A:V",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row_data]},
            ).execute()
            log.info("  Appended new row for %s", ai_result.get("company"))
    except Exception as e:
        log.error("  Failed to write to sheet: %s", e)


# ---------------------------------------------------------------------------
# 8. Main pipeline — processes one company
# ---------------------------------------------------------------------------
def process_company(company_config: dict, sheets_service, existing_rows: list[dict]) -> dict | None:
    """Process a single company: collect data → AI analysis → write to sheet."""
    name = company_config["name"]
    url = company_config["url"]
    monitoring = company_config.get("monitoring", {})

    log.info("=" * 60)
    log.info("Processing: %s (%s)", name, url)
    log.info("=" * 60)

    # Step 1: Fetch main website
    log.info("  Fetching website...")
    website_resp = safe_get(url, timeout=30)
    website_html = website_resp.text if website_resp and website_resp.status_code == 200 else ""

    if not website_html:
        log.warning("  Could not fetch website for %s", name)

    # Step 2: Parallel data collection
    region = company_config.get("region", "-")
    company_data = {
        "company": name,
        "url": url,
        "region": region,
        "youtube_activity": "-",
        "linkedin_activity": "-",
        "facebook_activity": "-",
        "social_count": 0,
        "g2_data": "-",
        "pages": {},
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        # YouTube
        if monitoring.get("socialMedia", {}).get("youtube") and website_html:
            futures["youtube"] = executor.submit(get_youtube_activity, website_html, name)

        # Social links
        if website_html:
            futures["social"] = executor.submit(detect_social_links, website_html)

        # Aggregators (Trustpilot + G2)
        futures["g2"] = executor.submit(get_aggregator_data, name, url)

        # Discover & fetch pages
        futures["urls"] = executor.submit(discover_urls, url)

        # Collect results
        for key, future in futures.items():
            try:
                result = future.result(timeout=60)
                if key == "youtube":
                    company_data["youtube_activity"] = result
                elif key == "social":
                    linkedin, facebook, all_social, count = format_social_activity(result)
                    company_data["linkedin_activity"] = linkedin
                    company_data["facebook_activity"] = facebook
                    company_data["social_count"] = count
                elif key == "g2":
                    company_data["g2_data"] = result
                elif key == "urls":
                    categorized_urls = result
            except Exception as e:
                log.warning("  Error in %s: %s", key, e)

    # Step 3: Fetch and parse categorized pages
    log.info("  Fetching %d categorized pages...", len(categorized_urls))
    pages_by_cat: dict[str, list] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        page_futures = {
            executor.submit(fetch_and_parse_page, item["url"], item["category"]): item
            for item in categorized_urls
        }
        for future in as_completed(page_futures):
            try:
                result = future.result(timeout=30)
                if result:
                    cat = result["category"]
                    pages_by_cat.setdefault(cat, []).append(result)
            except Exception:
                pass

    company_data["pages"] = pages_by_cat
    total_pages = sum(len(v) for v in pages_by_cat.values())
    log.info("  Parsed %d pages: %s", total_pages,
             {k: len(v) for k, v in pages_by_cat.items()})

    # Step 4: AI analysis
    log.info("  Sending to Claude for analysis...")
    ai_result = analyze_with_claude(company_data)

    # Ensure social/youtube/g2 data is in AI result (override if AI didn't fill)
    if ai_result.get("youtubeActivity") in (None, "", "-"):
        ai_result["youtubeActivity"] = company_data["youtube_activity"]
    if ai_result.get("linkedinActivity") in (None, "", "-"):
        ai_result["linkedinActivity"] = company_data["linkedin_activity"]
    if ai_result.get("facebookActivity") in (None, "", "-"):
        ai_result["facebookActivity"] = company_data["facebook_activity"]
    # Always use Python-parsed aggregator data (not Claude's rewrite)
    ai_result["aggregatorMentions"] = company_data["g2_data"]
    if ai_result.get("socialMentionsCount") in (None, 0, "0"):
        ai_result["socialMentionsCount"] = company_data["social_count"]

    # Ensure company/url/region are set
    ai_result["company"] = name
    ai_result["url"] = url
    ai_result["region"] = region

    # Step 5: Write to Google Sheets
    log.info("  Writing to Google Sheets...")
    write_to_sheet(sheets_service, ai_result, existing_rows)

    log.info("  Done: %s", name)
    return ai_result


# ---------------------------------------------------------------------------
# 9. Entry point
# ---------------------------------------------------------------------------
def load_companies_from_sheets(service) -> list[dict]:
    """Load companies from Google Sheets, enrich with companies.json data (region, priority)."""
    # Load enrichment data from JSON
    json_lookup = {}
    try:
        json_companies = load_companies_from_json()
        for c in json_companies:
            key = urlparse(c["url"]).netloc.replace("www.", "")
            json_lookup[key] = c
    except Exception:
        pass

    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=COMPANIES_SPREADSHEET_ID, range="Аркуш1!A:A")
            .execute()
        )
        values = result.get("values", [])
        companies = []
        for row in values[1:]:  # skip header
            url = row[0].strip() if row else ""
            if not url or not url.startswith("http"):
                continue
            name = extract_company_name(url)
            domain = urlparse(url).netloc.replace("www.", "")

            # Enrich from JSON if available
            json_data = json_lookup.get(domain, {})

            companies.append({
                "name": json_data.get("name", name),
                "url": url,
                "region": json_data.get("region", "-"),
                "priority": json_data.get("priority", "high"),
                "monitoring": json_data.get("monitoring", {
                    "website": True,
                    "blog": True,
                    "socialMedia": {"youtube": True, "facebook": True, "linkedin": True},
                }),
            })
        log.info("Loaded %d companies from Google Sheets", len(companies))
        return companies
    except Exception as e:
        log.warning("Failed to load from Sheets: %s — falling back to JSON", e)
        return load_companies_from_json()


def load_companies_from_json() -> list[dict]:
    """Fallback: load companies from config/companies.json."""
    with open(COMPANIES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", data if isinstance(data, list) else [])


def main():
    log.info("=" * 60)
    log.info("Competitor Monitoring System — Starting")
    log.info("=" * 60)

    # Validate config
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY is not set! Create .env file.")
        sys.exit(1)

    # Init Google Sheets
    sheets_service = get_sheets_service()

    # Load companies from Google Sheets (primary) or JSON (fallback)
    companies = load_companies_from_sheets(sheets_service)
    if not companies:
        companies = load_companies_from_json()
        log.info("Loaded %d companies from JSON fallback", len(companies))

    # Filter by priority if argument provided
    if len(sys.argv) > 1:
        filter_arg = sys.argv[1].lower()
        if filter_arg in ("high", "medium", "low"):
            companies = [c for c in companies if c.get("priority") == filter_arg]
            log.info("Filtered to %d %s-priority companies", len(companies), filter_arg)
        else:
            # Filter by company name
            companies = [
                c for c in companies
                if filter_arg in c["name"].lower()
            ]
            log.info("Filtered to %d companies matching '%s'", len(companies), filter_arg)

    if not companies:
        log.info("No companies to process.")
        return

    existing_rows = get_existing_rows(sheets_service)
    log.info("Found %d existing rows in sheet", len(existing_rows))

    # Process each company
    results = []
    for i, company in enumerate(companies, 1):
        log.info("\n[%d/%d] %s", i, len(companies), company["name"])
        try:
            result = process_company(company, sheets_service, existing_rows)
            if result:
                results.append(result)
        except Exception as e:
            log.error("Error processing %s: %s", company["name"], e)

        # Small delay between companies to avoid rate limits
        if i < len(companies):
            time.sleep(2)

    # Summary
    log.info("\n" + "=" * 60)
    log.info("DONE! Processed %d/%d companies", len(results), len(companies))
    log.info("=" * 60)


if __name__ == "__main__":
    main()


