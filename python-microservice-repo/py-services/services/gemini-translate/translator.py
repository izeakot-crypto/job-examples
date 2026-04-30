"""
Gemini Translation Engine.
Batch translation via Google Gemini API with validation and retry logic.
"""
import json
import re
import time
from collections import Counter
from typing import Optional

import requests

PROMPT_TEMPLATE = (
    "Translate to {target_lang}. CRITICAL: If text has ANY quotes or special characters "
    "around words - keep EXACT SAME characters, do NOT replace them! "
    "Example: \"Widgets\" -> \"Vidzhety\" (same \" quotes), NOT «Vidzhety». "
    "DANGEROUS characters: U+0027 APOSTROPHE, U+0022 QUOTATION MARK, U+201C U+201D. "
    "RULES: 1) Original has quotes/symbols = translation must have IDENTICAL quotes/symbols "
    "in same positions. 2) For NEW apostrophes in words (l'homme, im'ya, l'ora) use U+2019. "
    "3) For NEW quotes use: U+00AB U+00BB or U+201E U+201D. "
    "4) Preserve: %s %d {{var}} {{var}} \\n spaces. "
    "Return: [{{\"id\": N, \"translation\": \"...\"}}]. Input: {json_input}"
)

LANGUAGE_CODES = {
    "en": "English",
    "uk": "Ukrainian",
    "ru": "Russian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pl": "Polish",
    "pt": "Portuguese",
    "tr": "Turkish",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ka": "Georgian",
    "kk": "Kazakh",
    "ro": "Romanian",
}

API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _count_format_symbols(text: str) -> Counter:
    return Counter(re.findall(r"%\d*\$?[sdif]", text))


def _count_newlines(text: str) -> int:
    return text.count("\\n")


def _count_leading_trailing_spaces(text: str) -> tuple[int, int]:
    leading = len(text) - len(text.lstrip(" "))
    trailing = len(text) - len(text.rstrip(" "))
    return leading, trailing


def _extract_content_in_braces(text: str) -> list:
    return re.findall(r"\{+([^{}]+)\}+", text)


def _count_quotes(text: str) -> dict:
    return {
        "'": text.count("'"),
        '"': text.count('"'),
        "«": text.count("«"),
        "»": text.count("»"),
    }


def validate_translation(original: str, translation: str) -> tuple[bool, list[str]]:
    """Validate a translation against the original string.

    Returns (is_valid, list_of_error_messages).
    """
    errors = []

    if _count_format_symbols(original) != _count_format_symbols(translation):
        errors.append(
            f"Format symbols mismatch — expected: {dict(_count_format_symbols(original))}, "
            f"got: {dict(_count_format_symbols(translation))}"
        )

    if _count_newlines(original) != _count_newlines(translation):
        errors.append(
            f"Newline count mismatch — expected: {_count_newlines(original)}, "
            f"got: {_count_newlines(translation)}"
        )

    orig_lead, orig_trail = _count_leading_trailing_spaces(original)
    trans_lead, trans_trail = _count_leading_trailing_spaces(translation)
    if orig_lead != trans_lead or orig_trail != trans_trail:
        errors.append(
            f"Spacing mismatch — expected: lead={orig_lead}/trail={orig_trail}, "
            f"got: lead={trans_lead}/trail={trans_trail}"
        )

    orig_braces = _extract_content_in_braces(original)
    trans_braces = _extract_content_in_braces(translation)
    if orig_braces != trans_braces:
        errors.append(f"Braces content mismatch — expected: {orig_braces}, got: {trans_braces}")

    orig_quotes = _count_quotes(original)
    trans_quotes = _count_quotes(translation)
    if orig_quotes != trans_quotes:
        problems = [
            f"{q}: original={orig_quotes[q]}, translation={trans_quotes[q]}"
            for q in ["'", '"', "«", "»"]
            if orig_quotes[q] != trans_quotes[q]
        ]
        errors.append(f"Quotes mismatch — {', '.join(problems)}")

    return len(errors) == 0, errors


def _call_gemini_api(
    strings: list[str],
    target_lang: str,
    api_key: str,
    model: str,
    retry_ids: Optional[list[int]] = None,
    validation_errors: Optional[list[dict]] = None,
    retry_num: int = 0,
) -> Optional[list[str]]:
    """Send one batch request to Gemini API. Returns list of translations or None on failure."""
    if retry_ids:
        indexed_input = [{"id": retry_ids[i], "text": s} for i, s in enumerate(strings)]
    else:
        indexed_input = [{"id": i, "text": s} for i, s in enumerate(strings)]

    base_prompt = PROMPT_TEMPLATE.replace("{target_lang}", target_lang).replace(
        "{json_input}", json.dumps(indexed_input, ensure_ascii=False)
    )

    if validation_errors and retry_num > 0:
        error_lines = "\n".join(
            f"- ID {e['id']}: {e['error']}\n  Original: {e['original']}\n  Wrong: {e['translation']}"
            for e in validation_errors
        )
        prompt = f"\u26a0\ufe0f PREVIOUS ATTEMPT ERRORS:\n{error_lines}\n\nFIX these errors!\n\n{base_prompt}"
    else:
        prompt = base_prompt

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "translation": {"type": "string"},
                    },
                    "required": ["id", "translation"],
                },
            },
            "temperature": 0.3,
            "maxOutputTokens": 32000,
        },
    }

    api_url = API_URL_TEMPLATE.format(model=model)
    try:
        resp = requests.post(f"{api_url}?key={api_key}", json=payload, timeout=120)
        resp_json = resp.json()

        if "candidates" not in resp_json:
            return None

        raw = resp_json["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(raw)
        result_sorted = sorted(result, key=lambda x: x.get("id", 999))
        return [item.get("translation", "") for item in result_sorted]

    except (requests.exceptions.Timeout, requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return None


def translate_batch(
    strings: list[str],
    target_lang: str,
    api_key: str,
    model: str,
    max_retries: int = 8,
    sleep_between_retries: int = 10,
) -> tuple[list[str], list[dict]]:
    """Translate a batch of strings with retry on validation errors.

    Returns (translations, validation_failures).
    translations — same length as input strings.
    validation_failures — list of dicts with id/original/translation/errors for failed items.
    """
    translations: Optional[list[str]] = None
    validation_errors: Optional[list[dict]] = None

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            wait = sleep_between_retries * attempt
            time.sleep(wait)

        if attempt == 1:
            translations = _call_gemini_api(strings, target_lang, api_key, model)
        else:
            if validation_errors:
                failed_ids = [e["id"] for e in validation_errors]
                failed_strings = [strings[i] for i in failed_ids]
                partial = _call_gemini_api(
                    failed_strings,
                    target_lang,
                    api_key,
                    model,
                    retry_ids=failed_ids,
                    validation_errors=validation_errors,
                    retry_num=attempt - 1,
                )
                if partial is not None and translations is not None:
                    for i, fid in enumerate(failed_ids):
                        if i < len(partial):
                            translations[fid] = partial[i]
                else:
                    continue
            else:
                translations = _call_gemini_api(strings, target_lang, api_key, model)

        if translations is None:
            continue

        validation_errors = []
        for i, trans in enumerate(translations):
            if i < len(strings):
                is_valid, errors = validate_translation(strings[i], trans)
                if not is_valid:
                    validation_errors.append(
                        {
                            "id": i,
                            "original": strings[i],
                            "translation": trans,
                            "error": "; ".join(errors),
                        }
                    )

        if not validation_errors:
            return translations, []

    # Return partial result after all retries
    return translations or [""] * len(strings), validation_errors or []
