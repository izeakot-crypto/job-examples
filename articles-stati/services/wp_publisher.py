"""WordPress publishing orchestrator.

Fetches article from Supabase, transforms HTML, builds qTranslate strings,
generates meta descriptions via Claude, uploads image, creates WP draft post.
"""
import base64
import io
import logging
import re
from datetime import datetime, timezone

import httpx

from config import settings, LANGUAGES, DB_LANG_TO_QT
from services.anthropic_client import get_client as get_claude_client
from services.supabase_client import get_article_for_publish, get_client as get_supabase
from services.wordpress_client import WordPressClient
from utils.wp_html_transform import transform_for_wordpress

logger = logging.getLogger(__name__)

# DB column suffixes: en, ru, pl, es, tr, ua
_DB_SUFFIXES = {lang: DB_LANG_TO_QT[lang] for lang in LANGUAGES}
# qTranslate order
_QT_ORDER = ["ru", "ua", "en", "pl", "es", "tr"]


def _slugify_en(title: str) -> str:
    """Generate URL slug from English title."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:200]


def _build_qtranslate(values: dict[str, str]) -> str:
    """Build qTranslate string from {qt_lang: text} mapping."""
    parts = []
    for qt_lang in _QT_ORDER:
        text = values.get(qt_lang, "")
        parts.append(f"[:{qt_lang}]{text}")
    parts.append("[:]")
    return "".join(parts)


async def _generate_meta_description(title: str, lang_code: str) -> str:
    """Generate a 150-160 char meta description via Claude API."""
    client = get_claude_client()
    lang_names = {
        "en": "English", "ru": "Russian", "pl": "Polish",
        "es": "Spanish", "tr": "Turkish", "uk": "Ukrainian",
    }
    lang_name = lang_names.get(lang_code, "English")

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a meta description for an SEO article in {lang_name}. "
                    f"Article title: {title}\n\n"
                    f"Requirements:\n"
                    f"- Exactly 150-160 characters\n"
                    f"- In {lang_name} language\n"
                    f"- Engaging, includes a call to action\n"
                    f"- Output ONLY the meta description text, nothing else"
                ),
            }],
        )
        text = next((b for b in response.content if b.type == "text"), None)
        return text.text.strip() if text else ""
    except Exception as e:
        logger.warning(f"[WP] Meta description generation failed for {lang_code}: {e}")
        return ""


async def publish_to_wordpress(idea_id: str) -> dict:
    """Main publish flow: Supabase -> transform -> WP draft."""

    # Validate WP config
    if not settings.wp_base_url or not settings.wp_app_password:
        return {"success": False, "error": "WordPress credentials not configured"}

    wp = WordPressClient(settings.wp_base_url, settings.wp_username, settings.wp_app_password)

    # 1. Fetch article + idea from DB
    try:
        data = get_article_for_publish(idea_id)
    except Exception as e:
        logger.error(f"[WP] Failed to fetch article {idea_id}: {e}")
        return {"success": False, "error": f"Article not found: {e}"}

    idea = data.get("idea", {})

    # Idempotency: if already published to WP, update instead of create
    existing_wp_id = data.get("wordpress_post_id")

    # 2. Validate all 6 translations exist
    titles = {}   # qt_lang -> title
    contents = {} # qt_lang -> transformed html
    for db_lang in LANGUAGES:
        qt_lang = DB_LANG_TO_QT[db_lang]
        suffix = _DB_SUFFIXES[db_lang]
        content = data.get(f"translation_{suffix}", "")
        title = data.get(f"theme_{suffix}", "")
        if not content:
            return {
                "success": False,
                "error": f"Missing translation for language: {db_lang} (column: translation_{suffix})",
            }
        if not title:
            return {
                "success": False,
                "error": f"Missing title for language: {db_lang} (column: theme_{suffix})",
            }
        titles[qt_lang] = title
        contents[qt_lang] = transform_for_wordpress(content)

    # 3. Build qTranslate strings
    qt_title = _build_qtranslate(titles)
    qt_content = _build_qtranslate(contents)

    # 4. Generate meta descriptions via Claude (sequential, proxy concurrency=1)
    meta_descs = {}
    for db_lang in LANGUAGES:
        qt_lang = DB_LANG_TO_QT[db_lang]
        title = titles[qt_lang]
        desc = await _generate_meta_description(title, db_lang)
        meta_descs[qt_lang] = desc
        logger.info(f"[WP] Meta desc {qt_lang}: {len(desc)} chars")

    qt_meta_desc = _build_qtranslate(meta_descs)

    # 5. Generate slug from English title
    en_title = titles.get("en", "article")
    slug = _slugify_en(en_title)

    # 6. Keywords from idea
    keywords = idea.get("keywords", [])
    if isinstance(keywords, list):
        keywords_str = ", ".join(keywords)
    else:
        keywords_str = str(keywords)

    # 7. Download and upload article image
    media_id = None
    image_value = data.get("article_image", "")
    if image_value:
        try:
            if image_value.startswith("data:"):
                # Base64 data URI: data:image/png;base64,iVBOR...
                header, b64data = image_value.split(",", 1)
                image_bytes = base64.b64decode(b64data)
                # Extract mime from header: data:image/png;base64
                mime = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
                ext = mime.split("/")[1] if "/" in mime else "png"
                fname = f"{slug}.{ext}"
                logger.info(f"[WP] Image from base64 data URI, mime={mime}, size={len(image_bytes)}")
            else:
                # URL (Supabase Storage or external)
                async with httpx.AsyncClient(timeout=30.0) as http:
                    img_resp = await http.get(image_value)
                    img_resp.raise_for_status()
                    image_bytes = img_resp.content

                if ".png" in image_value.lower():
                    fname, mime = f"{slug}.png", "image/png"
                elif ".webp" in image_value.lower():
                    fname, mime = f"{slug}.webp", "image/webp"
                else:
                    fname, mime = f"{slug}.jpg", "image/jpeg"
                logger.info(f"[WP] Image downloaded from URL, size={len(image_bytes)}")

            # Compress large images: convert PNG to JPEG if > 500KB
            if len(image_bytes) > 500_000:
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(image_bytes))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85, optimize=True)
                    image_bytes = buf.getvalue()
                    fname = f"{slug}.jpg"
                    mime = "image/jpeg"
                    logger.info(f"[WP] Compressed to JPEG: {len(image_bytes)} bytes")
                except ImportError:
                    logger.warning("[WP] Pillow not installed, uploading original size")

            media_id = await wp.upload_media(image_bytes, fname, mime)
            logger.info(f"[WP] Image uploaded to WP: media_id={media_id}")
        except Exception as e:
            logger.error(f"[WP] Image upload failed: {e}")
            return {"success": False, "error": f"Image upload failed: {e}"}
    else:
        logger.warning(f"[WP] No article_image found, creating post without featured image")

    # 8. Get blog category
    blog_cat_id = await wp.get_category_id("blog")

    # 9. Build post data
    post_data = {
        "title": qt_title,
        "content": qt_content,
        "excerpt": qt_meta_desc,
        "slug": slug,
        "status": "draft",
        "meta": {
            "_yoast_wpseo_metadesc": qt_meta_desc,
            "_yoast_wpseo_focuskw": keywords_str,
        },
    }
    if blog_cat_id:
        post_data["categories"] = [blog_cat_id]
    if media_id:
        post_data["featured_media"] = media_id

    # 10. Create or update WP post
    try:
        if existing_wp_id:
            wp_result = await wp.update_post(int(existing_wp_id), post_data)
            logger.info(f"[WP] Updated existing post {existing_wp_id}")
        else:
            wp_result = await wp.create_post(post_data)
            logger.info(f"[WP] Created new post {wp_result['id']}")
    except Exception as e:
        logger.error(f"[WP] Post creation failed: {e}")
        return {"success": False, "error": f"WordPress post creation failed: {e}"}

    # 11. Update DB with WP info
    now = datetime.now(timezone.utc).isoformat()
    try:
        client = get_supabase()
        client.table("articles_audit").update({
            "status": "published",
            "updated_at": now,
            "wordpress_post_id": wp_result["id"],
            "wordpress_url": wp_result["link"],
        }).eq("id", idea_id).execute()

        client.table("ideas").update({
            "status": "published",
        }).eq("id", idea_id).execute()

        logger.info(f"[WP] DB updated for {idea_id}")
    except Exception as e:
        logger.warning(f"[WP] DB update failed (post was created): {e}")

    wp_id = wp_result["id"]
    return {
        "success": True,
        "wordpress_post_id": wp_id,
        "wordpress_url": wp_result["link"],
        "admin_url": f"{settings.wp_base_url}/wp-admin/post.php?post={wp_id}&action=edit",
        "status": "draft",
        "idea_id": idea_id,
        "timestamp": now,
    }
