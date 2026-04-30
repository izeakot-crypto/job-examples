"""WF2: Article Verification — fully self-hosted.

Replaces browser-automated ZeroGPT, Copyleaks, Advego with:
- text_stats.py — water %, nausea (local math)
- ai_detector.py — Claude proxy AI detection
- self_plagiarism.py — shingle comparison against own articles
- google_checker.py — Google Search spot-check (optional)

If a language fails, calls WF3 (Regeneration) and re-verifies.
On pass, saves to Supabase and notifies frontend.
"""
import asyncio
import logging
import re
from dataclasses import dataclass

from config import (
    LANGUAGES,
    ADVEGO_NAUSEA_RANGE,
    ADVEGO_WATER_RANGE,
    settings,
)
from services.anthropic_client import generate_meta_description
from services.progress import notify_progress, notify_frontend_save
from services.supabase_client import update_article_audit
from services.verification.text_stats import check_text_stats
from services.verification.ai_detector import check_ai_detection
from services.verification.self_plagiarism import check_self_plagiarism
from services.verification.google_checker import check_google_uniqueness
from pipeline.regenerator import regenerate_language
from utils.html_utils import strip_html

logger = logging.getLogger(__name__)

# Map between internal lang codes and field suffixes
LANG_SUFFIX = {"en": "en", "ru": "ru", "pl": "pl", "es": "es", "tr": "tr", "uk": "ua"}

# Thresholds
AI_DETECTION_FAIL = 95      # % — above this = definitely AI, needs regen (proxy gives 80-85% for normal AI text)
AI_DETECTION_WARN = 80      # % — above this = suspicious
SELF_PLAGIARISM_FAIL = 25   # % — above this = too similar to own articles
GOOGLE_UNIQUENESS_FAIL = 60 # % — below this = too many matches found
MIN_UL_LISTS = 2            # minimum <ul> lists required in article


@dataclass
class VerificationResult:
    lang: str
    # Text stats (replaces Advego)
    water: float = 0.0
    academic_nausea: float = 0.0
    classic_nausea: float = 0.0
    word_count: int = 0
    # AI detection (replaces ZeroGPT + Copyleaks)
    ai_probability: float = 0.0
    ai_confidence: str = "low"
    # Self-plagiarism
    self_similarity: float = 0.0
    # Google uniqueness
    google_uniqueness: float = 100.0
    # HTML structure
    ul_count: int = 0
    # Verdict
    needs_regeneration: bool = False
    regeneration_reason: str = ""
    status: str = "pass"


def _evaluate_thresholds(vr: VerificationResult, html_content: str = "") -> VerificationResult:
    """Apply quality thresholds and determine pass/fail."""
    reasons = []

    # AI detection
    if vr.ai_probability >= AI_DETECTION_FAIL:
        reasons.append(f"AI: {vr.ai_probability}% (>{AI_DETECTION_FAIL}% = fail)")

    # Nausea (academic)
    nmin, nmax = ADVEGO_NAUSEA_RANGE
    if vr.academic_nausea < nmin:
        reasons.append(f"nausea {vr.academic_nausea}% (<{nmin}%)")
    elif vr.academic_nausea > nmax:
        reasons.append(f"nausea {vr.academic_nausea}% (>{nmax}%)")

    # Water
    wmin, wmax = ADVEGO_WATER_RANGE
    if vr.water < wmin:
        reasons.append(f"water {vr.water}% (<{wmin}%)")
    elif vr.water > wmax:
        reasons.append(f"water {vr.water}% (>{wmax}%)")

    # Self-plagiarism
    if vr.self_similarity > SELF_PLAGIARISM_FAIL:
        reasons.append(f"self-plagiarism {vr.self_similarity}% (>{SELF_PLAGIARISM_FAIL}%)")

    # Google uniqueness
    if vr.google_uniqueness < GOOGLE_UNIQUENESS_FAIL:
        reasons.append(f"uniqueness {vr.google_uniqueness}% (<{GOOGLE_UNIQUENESS_FAIL}%)")

    # HTML structure — require bullet lists
    if html_content:
        vr.ul_count = len(re.findall(r"<ul[\s>]", html_content, re.IGNORECASE))
        if vr.ul_count < MIN_UL_LISTS:
            reasons.append(f"missing <ul> lists: found {vr.ul_count}, need at least {MIN_UL_LISTS}")

    vr.needs_regeneration = len(reasons) > 0
    vr.regeneration_reason = "; ".join(reasons) if reasons else ""

    if vr.needs_regeneration:
        vr.status = "fail"
    elif vr.ai_probability > AI_DETECTION_WARN:
        vr.status = "warning"
    else:
        vr.status = "pass"

    return vr


async def _run_all_checks(article_data: dict) -> dict[str, VerificationResult]:
    """Run all verification checks for all languages."""
    # Collect texts per language
    texts = {}
    for lang in LANGUAGES:
        suffix = LANG_SUFFIX[lang]
        content = article_data.get(f"translation_{suffix}", "")
        if content:
            texts[lang] = content

    idea_id = article_data.get("idea_id", "")

    # Prepare plain texts for AI detection
    plain_texts = {lang: strip_html(content) for lang, content in texts.items()}

    # Run all checks in parallel
    stats_task = asyncio.to_thread(check_text_stats, texts)
    ai_task = check_ai_detection(plain_texts)
    plagiarism_task = check_self_plagiarism(texts, idea_id)
    google_task = check_google_uniqueness(texts)

    stats_results, ai_results, plagiarism_results, google_results = await asyncio.gather(
        stats_task, ai_task, plagiarism_task, google_task,
    )

    # Build verification results (only for languages that have content)
    results = {}
    for lang in LANGUAGES:
        if lang not in texts:
            # No content for this language — skip, don't mark as fail
            results[lang] = VerificationResult(lang=lang, status="skipped")
            continue

        vr = VerificationResult(lang=lang)

        # Text stats
        stats = stats_results.get(lang, {})
        vr.water = stats.get("water", 0.0)
        vr.academic_nausea = stats.get("academic_nausea", 0.0)
        vr.classic_nausea = stats.get("classic_nausea", 0.0)
        vr.word_count = stats.get("word_count", 0)

        # AI detection
        ai = ai_results.get(lang, {})
        vr.ai_probability = ai.get("ai_probability", 0.0)
        vr.ai_confidence = ai.get("confidence", "low")

        # Self-plagiarism
        plag = plagiarism_results.get(lang, {})
        vr.self_similarity = plag.get("similarity", 0.0)

        # Google uniqueness
        google = google_results.get(lang, {})
        vr.google_uniqueness = google.get("uniqueness", 100.0)

        results[lang] = _evaluate_thresholds(vr, html_content=texts.get(lang, ""))

    return results


async def run_verification(article_data: dict, max_regen_cycles: int = 2) -> dict:
    """Main entry point for WF2.

    Runs verification checks, regenerates failed languages, re-checks.
    Returns final merged result.
    """
    idea_id = article_data.get("idea_id", "unknown")
    await notify_progress(idea_id, "verifying", 70, "Перевірка статті...")

    current_data = dict(article_data)
    verification_attempts = 0

    for cycle in range(max_regen_cycles + 1):
        verification_attempts += 1
        logger.info(f"Verification cycle {cycle + 1}")

        # Run all checks
        results = await _run_all_checks(current_data)

        # Log results
        for lang, vr in results.items():
            status_icon = "PASS" if not vr.needs_regeneration else "FAIL"
            logger.info(
                f"  [{lang}] {status_icon} — AI:{vr.ai_probability}% "
                f"Water:{vr.water}% Nausea:{vr.academic_nausea}% "
                f"SelfPlag:{vr.self_similarity}% Google:{vr.google_uniqueness}% "
                f"Lists:{vr.ul_count}"
            )

        # Find languages that need regeneration
        failed_langs = [lang for lang, vr in results.items() if vr.needs_regeneration]

        if not failed_langs:
            logger.info("All languages passed verification!")
            break

        if cycle >= max_regen_cycles:
            logger.warning(f"Max regen cycles reached. Failed langs: {failed_langs}")
            break

        # Regenerate failed languages sequentially (proxy concurrency limit)
        logger.info(f"Regenerating: {failed_langs}")
        for lang in failed_langs:
            try:
                regen_result = await regenerate_language(
                    lang=lang,
                    idea_id=current_data.get("idea_id"),
                    theme=current_data.get("theme", ""),
                    reason=results[lang].regeneration_reason,
                )
                suffix = LANG_SUFFIX[lang]
                if regen_result.get("content"):
                    current_data[f"translation_{suffix}"] = regen_result["content"]
                    if regen_result.get("title"):
                        current_data[f"theme_{suffix}"] = regen_result["title"]
            except Exception as e:
                logger.error(f"[{lang}] Regeneration failed: {e}")
            await asyncio.sleep(3)

    # Build final result
    final = _build_final_result(current_data, results)

    # Save to Supabase and notify frontend
    await _save_results(idea_id, current_data, results, verification_attempts)
    await notify_progress(idea_id, "review_ready", 100, "Стаття успішно загружена")

    # Auto-generate image after verification
    try:
        from services.image_gen.generator import generate_image
        from services.supabase_client import patch_article_audit
        import re as _re
        theme = current_data.get("theme", "")
        description = current_data.get("translation_en", "") or current_data.get("translation_ua", "")
        description = _re.sub(r"<[^>]+>", " ", description)[:1000].strip()
        logger.info("[Image] Auto-generating image for %s", idea_id)
        img_result = await generate_image(theme, description)
        if img_result.get("success") and img_result.get("imageBase64"):
            mime = img_result.get("mimeType", "image/png")
            b64 = img_result["imageBase64"]
            image_data = b64 if b64.startswith("data:") else "data:" + mime + ";base64," + b64
            await asyncio.to_thread(patch_article_audit, idea_id, {"article_image": image_data})
            logger.info("[Image] Auto-generated and saved for %s", idea_id)
        else:
            logger.warning("[Image] Auto-generation failed: %s", img_result.get("error"))
    except Exception as e:
        logger.warning("[Image] Auto-generation error (non-fatal): %s", e)

    return final


def _build_final_result(data: dict, results: dict[str, VerificationResult]) -> dict:
    merged = {
        "idea_id": data.get("idea_id"),
        "theme": data.get("theme"),
        "verification_status": "pass",
    }

    for lang, vr in results.items():
        suffix = LANG_SUFFIX[lang]
        merged[f"translation_{suffix}"] = data.get(f"translation_{suffix}", "")
        merged[f"theme_{suffix}"] = data.get(f"theme_{suffix}", "")
        merged[f"ai_detection_{suffix}"] = vr.ai_probability
        merged[f"water_{suffix}"] = vr.water
        merged[f"nausea_{suffix}"] = vr.academic_nausea

        if vr.needs_regeneration:
            merged["verification_status"] = "fail"

    return merged


async def _save_results(
    idea_id: str, data: dict, results: dict[str, VerificationResult], attempts: int = 1,
):
    """Save verification results to Supabase and notify frontend."""
    from datetime import datetime, timezone

    # Build verification_report JSON — per-language detailed metrics
    verification_report = {}
    for lang, vr in results.items():
        verification_report[lang] = {
            "status": vr.status,
            "ai_probability": vr.ai_probability,
            "ai_confidence": vr.ai_confidence,
            "water": vr.water,
            "academic_nausea": vr.academic_nausea,
            "classic_nausea": vr.classic_nausea,
            "word_count": vr.word_count,
            "self_similarity": vr.self_similarity,
            "google_uniqueness": vr.google_uniqueness,
            "ul_count": vr.ul_count,
            "needs_regeneration": vr.needs_regeneration,
            "regeneration_reason": vr.regeneration_reason,
        }

    # Generate SEO meta descriptions per language (keyed by DB suffix, e.g. ua/en/ru)
    meta_description = {}
    for lang in LANGUAGES:
        suffix = LANG_SUFFIX[lang]
        content = data.get(f"translation_{suffix}", "")
        if not content:
            continue
        title = data.get(f"theme_{suffix}") or data.get("theme", "")
        try:
            meta = await generate_meta_description(lang, title, content)
            if meta:
                meta_description[suffix] = meta
        except Exception as e:
            logger.error(f"[{lang}] meta description failed: {e}")
        # Stagger calls to respect Claude proxy concurrency limit
        await asyncio.sleep(2)

    # Save to DB
    db_data = {
        "verification_status": "pass" if all(not vr.needs_regeneration for vr in results.values()) else "fail",
        "verification_attempts": attempts,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "theme_ua": data.get("theme"),
        "verification_report": verification_report,
        "meta_description": meta_description,
        "overall_status": "passed" if all(not vr.needs_regeneration for vr in results.values()) else "failed",
    }
    for lang in LANGUAGES:
        suffix = LANG_SUFFIX[lang]
        vr = results.get(lang)
        db_data[f"translation_{suffix}"] = data.get(f"translation_{suffix}", "")
        if suffix != "ua":
            db_data[f"theme_{suffix}"] = data.get(f"theme_{suffix}", "")
        # Per-language metric columns (kept for backward compat)
        if vr and vr.status != "skipped":
            db_data[f"ai_{suffix}"] = vr.ai_probability
            db_data[f"zerogpt_{suffix}"] = vr.ai_probability
            # uniqueness = 100 - self_similarity (or google_uniqueness if lower)
            uniq = min(100.0 - vr.self_similarity, vr.google_uniqueness)
            db_data[f"uniqueness_{suffix}"] = max(0.0, uniq)
            db_data[f"status_{suffix}"] = vr.status

    try:
        await asyncio.to_thread(update_article_audit, idea_id, db_data)
    except Exception as e:
        logger.error(f"Failed to save to DB: {e}")

    # Notify frontend
    frontend_data = {
        "id": idea_id,
        "theme": data.get("theme", ""),
        "verification_status": db_data["verification_status"],
    }
    for lang in LANGUAGES:
        suffix = LANG_SUFFIX[lang]
        frontend_data[f"translation_{suffix}"] = data.get(f"translation_{suffix}", "")

    await notify_frontend_save(frontend_data)
