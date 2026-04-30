#!/usr/bin/env python3
import json, re, fcntl, time, requests, sys, os
from collections import Counter

# Config
API_KEY = "AIzaSyAzONP6BJ4XjQ-Gaqssao09pjC7eOOtH38"
MODEL = "gemini-2.5-pro"
BATCH_SIZE = 100
SLEEP_SEC = 30
MAX_RETRIES = 8

API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
CONFIG = "prompt_config.json"
LOCK_FILE = ".translate.lock"

# Import all functions from translate_json_final.py
def translate_batch(strings, lang, cfg, show_prompt=False, retry_num=0, validation_errors=None, retry_ids=None):
    if retry_ids:
        indexed_input = [{"id": retry_ids[i], "text": s} for i, s in enumerate(strings)]
    else:
        indexed_input = [{"id": i, "text": s} for i, s in enumerate(strings)]

    base_prompt = cfg['prompt_template'].replace('{target_lang}', lang).replace('{json_input}', json.dumps(indexed_input, ensure_ascii=False))

    if validation_errors and retry_num > 0:
        error_text = "⚠️ PREVIOUS ATTEMPT CONTAINED ERRORS:\n"
        for err in validation_errors:
            error_text += f"- ID {err['id']}: {err['error']}\n"
            error_text += f"  Original: {err['original']}\n"
            error_text += f"  Wrong translation: {err['translation']}\n"
        error_text += "\nFIX these errors! Remember all the rules:\n\n"
        prompt = error_text + base_prompt
    else:
        prompt = base_prompt

    if show_prompt or (retry_num > 0 and validation_errors):
        print(f"\n📝 Prompt for batch (attempt {retry_num + 1}):\n{prompt}\n")

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "translation": {"type": "string"}
                    },
                    "required": ["id", "translation"]
                }
            },
            "temperature": 0.3,
            "maxOutputTokens": 32000
        }
    }

    try:
        resp = requests.post(f"{API_URL}?key={API_KEY}", json=payload, timeout=120)
        resp_json = resp.json()

        if 'candidates' not in resp_json:
            print(f"❌ Error response: {json.dumps(resp_json, ensure_ascii=False)}")
            return None

        finish_reason = resp_json['candidates'][0].get('finishReason', 'UNKNOWN')
        if finish_reason not in ['STOP', 'MAX_TOKENS']:
            print(f"⚠️  Unexpected finish reason: {finish_reason}")

        raw = resp_json['candidates'][0]['content']['parts'][0]['text']
        result = json.loads(raw)
        result_sorted = sorted(result, key=lambda x: x.get('id', 999))

        expected_ids = set(range(len(strings)))
        received_ids = {item.get('id') for item in result_sorted}
        missing_ids = expected_ids - received_ids

        if missing_ids:
            print(f"⚠️  Missing translations for IDs: {sorted(missing_ids)}")

        translations = [item.get('translation', '') for item in result_sorted]
        return translations

    except requests.exceptions.Timeout:
        print(f"❌ Request timeout after 120s")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        if 'raw' in locals():
            print(f"Raw response:\n{raw}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def extract_content_in_braces(text):
    pattern = r'\{+([^{}]+)\}+'
    matches = re.findall(pattern, text)
    return matches

def count_newlines(text):
    return text.count('\\n')

def count_leading_trailing_spaces(text):
    leading = len(text) - len(text.lstrip(' '))
    trailing = len(text) - len(text.rstrip(' '))
    return leading, trailing

def count_format_symbols(text):
    return Counter(re.findall(r'%\d*\$?[sdif]', text))

def count_quotes(text):
    quotes = {}
    quotes["'"] = text.count("'")
    quotes['"'] = text.count('"')
    quotes['«'] = text.count('«')
    quotes['»'] = text.count('»')
    return quotes

def validate_translation(orig, trans, item_id=None):
    errors = []

    orig_symbols = count_format_symbols(orig)
    trans_symbols = count_format_symbols(trans)
    if orig_symbols != trans_symbols:
        errors.append(f"Format symbols mismatch - Expected: {orig_symbols}, Got: {trans_symbols}")

    orig_newlines = count_newlines(orig)
    trans_newlines = count_newlines(trans)
    if orig_newlines != trans_newlines:
        errors.append(f"Newline count mismatch - Expected: {orig_newlines}, Got: {trans_newlines}")

    orig_lead, orig_trail = count_leading_trailing_spaces(orig)
    trans_lead, trans_trail = count_leading_trailing_spaces(trans)
    if orig_lead != trans_lead or orig_trail != trans_trail:
        errors.append(f"Spacing mismatch - Expected: lead={orig_lead}/trail={orig_trail}, Got: lead={trans_lead}/trail={trans_trail}")

    orig_braces = extract_content_in_braces(orig)
    trans_braces = extract_content_in_braces(trans)
    if orig_braces != trans_braces:
        errors.append(f"Braces content mismatch - Expected: {orig_braces}, Got: {trans_braces}")

    orig_quotes = count_quotes(orig)
    trans_quotes = count_quotes(trans)
    if orig_quotes != trans_quotes:
        problems = []
        for q_type in ["'", '"', '«', '»']:
            orig_count = orig_quotes.get(q_type, 0)
            trans_count = trans_quotes.get(q_type, 0)
            if orig_count != trans_count:
                orig_str = f"{orig_count}" if orig_count > 0 else "none"
                trans_str = f"{trans_count}" if trans_count > 0 else "none"
                problems.append(f"{q_type}: Original={orig_str}, Translation={trans_str}")
        errors.append(f"Quotes mismatch try another Quote, do not add new \"\" or '' - {', '.join(problems)}")

    if errors:
        print(f"⚠️  Validation failed (ID {item_id}):")
        print(f"  Original: {orig}")
        print(f"  Translation: {trans}")
        for error in errors:
            print(f"  - {error}")
        return False, errors

    return True, []

def translate_batch_with_retry(strings, lang, cfg, show_prompt=False):
    validation_errors_list = None
    translations = None
    retry_reason = None

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            wait_time = 10 * attempt
            reason_msg = f" (Reason: {retry_reason})" if retry_reason else ""
            print(f"🔄 Retry attempt {attempt}/{MAX_RETRIES} after {wait_time}s...{reason_msg}")
            time.sleep(wait_time)

        if attempt == 1:
            translations = translate_batch(strings, lang, cfg, show_prompt, attempt - 1, validation_errors_list)
        else:
            if validation_errors_list:
                failed_ids = [err['id'] for err in validation_errors_list]
                failed_strings = [strings[i] for i in failed_ids]

                print(f"🎯 Retrying only {len(failed_strings)} failed items (IDs: {failed_ids})")

                retry_translations = translate_batch(failed_strings, lang, cfg, show_prompt, attempt - 1, validation_errors_list, retry_ids=failed_ids)

                if retry_translations is not None:
                    for i, failed_id in enumerate(failed_ids):
                        if i < len(retry_translations):
                            translations[failed_id] = retry_translations[i]
                else:
                    retry_reason = "API request failed (timeout, 503, or error)"
                    continue
            else:
                print(f"🔄 Retrying full batch after API error")
                translations = translate_batch(strings, lang, cfg, False, attempt - 1, None)

        if translations is None:
            retry_reason = "API request failed (timeout, 503, or error)"
            continue

        all_valid = True
        validation_errors_list = []

        for i, trans in enumerate(translations):
            if i < len(strings):
                is_valid, errors = validate_translation(strings[i], trans, i)
                if not is_valid:
                    all_valid = False
                    validation_errors_list.append({
                        'id': i,
                        'original': strings[i],
                        'translation': trans,
                        'error': '; '.join(errors)
                    })

        if all_valid:
            if attempt > 1:
                print(f"✅ Retry successful on attempt {attempt}")
            return translations
        else:
            print(f"❌ Validation failed for {len(validation_errors_list)} items")
            retry_reason = f"Validation errors in {len(validation_errors_list)} translations"

    print(f"❌ All {MAX_RETRIES} attempts failed")
    return translations

def main(json_file):
    with open(CONFIG, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    fname = os.path.basename(json_file)
    lang_code = fname.split('_')[0] if '_' in fname else 'en'
    target_lang = cfg['language_codes'].get(lang_code, 'English')

    print(f"🔍 Resume mode: translating only empty translations")
    print(f"🌐 Target language: {target_lang} ({lang_code})")
    print(f"🤖 Model: {MODEL}")
    print(f"🔄 Max retries: {MAX_RETRIES}")

    with open(LOCK_FILE, 'a') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        print("🔒 Lock acquired")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Find empty translations
        empty_indices = []
        empty_originals = []
        for i, item in enumerate(data):
            if not item.get('translation') or item['translation'].strip() == '':
                empty_indices.append(i)
                empty_originals.append(item['original'])

        if not empty_indices:
            print("✅ No empty translations found! All done.")
            fcntl.flock(lf, fcntl.LOCK_UN)
            return

        total = len(empty_indices)
        batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"📦 Found {total} empty translations in {batches} batches (size={BATCH_SIZE})")
        print(f"📍 Indices: {empty_indices[:10]}{'...' if len(empty_indices) > 10 else ''}")

        # Process batches
        failed_batches = []
        for num in range(batches):
            start = num * BATCH_SIZE
            end = min(start + BATCH_SIZE, total)

            batch_originals = empty_originals[start:end]
            batch_indices = empty_indices[start:end]

            show_prompt = (num == 0)

            print(f"\n📤 Processing batch {num+1}/{batches} ({len(batch_originals)} items)...")
            translations = translate_batch_with_retry(batch_originals, target_lang, cfg, show_prompt)

            if translations is None:
                print(f"❌ Batch {num+1}/{batches} failed after {MAX_RETRIES} attempts")
                failed_batches.append(num+1)
                continue

            # Update only these positions in original data
            valid_count = 0
            for i, trans in enumerate(translations):
                if i < len(batch_indices):
                    original_idx = batch_indices[i]
                    is_valid, _ = validate_translation(batch_originals[i], trans, i)
                    if is_valid:
                        valid_count += 1
                    data[original_idx]['translation'] = trans

            print(f"✅ Batch {num+1}/{batches}: {len(translations)} translated, {valid_count} validated")

            if num < batches - 1 and SLEEP_SEC > 0:
                print(f"💤 Sleeping {SLEEP_SEC}s...")
                time.sleep(SLEEP_SEC)

        # Save result
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Saved to {json_file}")

        if failed_batches:
            print(f"⚠️  Failed batches: {failed_batches} (total: {len(failed_batches)})")
        else:
            print(f"✅ All batches completed successfully!")

        fcntl.flock(lf, fcntl.LOCK_UN)
        print("🔓 Lock released")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: translate_json_resume.py <file_done.json>")
        sys.exit(1)
    main(sys.argv[1])
