#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализатор качества переводов.
Этап A: программные проверки (плейсхолдеры, кавычки, длина)
Этап B: LLM-анализ (оригинал + переводы)
"""
from shared.logger import get_logger
from .llm_client import LLMClient, parse_llm_json
from .text_utils import (
    preprocess_text, restore_placeholders, restore_quotes,
    count_placeholders, count_quotes, _ALL_QUOTE_CHARS
)

logger = get_logger("translation-checker.analyzer")

# Языки для проверки
KNOWN_LANGS = {
    'de_DE', 'en_US', 'fr_FR', 'ka_GE', 'it_IT', 'kk_KZ',
    'pl_PL', 'pt_PT', 'ro_RO', 'es_ES', 'tr_TR', 'uk_UA'
}

LANG_NAMES = {
    'de_DE': 'Немецкий',
    'en_US': 'Английский',
    'fr_FR': 'Французский',
    'ka_GE': 'Грузинский',
    'it_IT': 'Итальянский',
    'kk_KZ': 'Казахский',
    'pl_PL': 'Польский',
    'pt_PT': 'Португальский',
    'ro_RO': 'Румынский',
    'es_ES': 'Испанский',
    'tr_TR': 'Турецкий',
    'uk_UA': 'Украинский',
}

ORIGINAL_CHECK_PROMPT = """Ты — профессиональный корректор русского языка и эксперт по локализации ПО.
Проверь этот текст UI-интерфейса на русском языке.

Текст: "{text}"

Проверь ТОЛЬКО на:
1. Орфографические ошибки (неправильное написание слов)
2. Грубые грамматические ошибки (неверные падежи, род, число)
3. Пунктуацию, которая МЕНЯЕТ СМЫСЛ

НЕ считай проблемами:
- Технические термины (SIP, IVR, CRM, API, callback и т.д.)
- Плейсхолдеры (%s, %d, [PLACEHOLDER], [TEMPLATE])
- Фразы без подлежащего/сказуемого (нормально для UI)
- Отсутствие точки в конце
- Стилистические предпочтения
- ё/е варианты (оба допустимы)

Будь ОЧЕНЬ строгим: отмечай только ЯВНЫЕ ошибки. Если сомневаешься — НЕ включай.

Ответ в JSON:
[{{"issue": "описание проблемы", "severity": "high|medium", "fix": "исправленный текст"}}]
Если ошибок нет — верни: []"""

TRANSLATION_CHECK_PROMPT = """Ты — эксперт по локализации ПО. Проверь переводы UI-текста.

Оригинал (русский): "{original}"

Переводы:
{translations}

Проверь КАЖДЫЙ перевод СТРОГО ТОЛЬКО на:
1. ГРУБЫЕ ошибки перевода — смысл ЯВНО искажён или потерян
2. Пропущенные/лишние переменные (%s, %d, {{{{...}}}})
3. Перевод ЯВНО не соответствует оригиналу (совсем другой смысл)
4. Пустой перевод при непустом оригинале

НЕ СЧИТАЙ ПРОБЛЕМАМИ (это НОРМАЛЬНО):
- Стилистические различия и синонимы
- Разный порядок слов (если смысл сохранён)
- Отсутствие/наличие точки в конце
- Незначительные отличия в формулировках
- Разные типы кавычек в разных языках (это допустимо)
- Адаптация текста под грамматику целевого языка

ВАЖНО: Будь КРАЙНЕ СТРОГИМ к себе. Отмечай ТОЛЬКО то, что ТОЧНО является ошибкой.
Переводы делает профессиональный переводчик — доверяй его решениям.
Если хоть немного сомневаешься — НЕ включай в список.

Ответ СТРОГО в JSON:
[{{"lang": "xx_XX", "issue": "краткое описание проблемы", "severity": "high|medium", "fix": "предложенное исправление"}}]
Если ВСЁ в порядке — верни: []"""


class TranslationAnalyzer:
    """Анализирует качество оригинала и переводов."""

    def __init__(self, client: LLMClient, config: dict):
        self.client = client
        self.check_original = config.get('check_original', True)
        self.check_translations = config.get('check_translations', True)
        self.max_length_ratio = config.get('max_length_ratio', 3.0)
        self.min_length_ratio = config.get('min_length_ratio', 0.2)

    def analyze(self, item: dict) -> dict:
        """Полный анализ одного элемента перевода."""
        original = item.get('Оригинал', '').strip()
        if not original:
            return None

        translations = {}
        for key, value in item.items():
            if key != 'Оригинал' and isinstance(value, str) and value.strip():
                translations[key] = value.strip()

        all_problems = []

        code_problems = self._check_code(original, translations)
        all_problems.extend(code_problems)

        if self.check_original and len(original.split()) >= 3:
            orig_problems = self._check_original_llm(original)
            all_problems.extend(orig_problems)

        if self.check_translations and translations:
            trans_problems = self._check_translations_llm(original, translations)
            all_problems.extend(trans_problems)

        if not all_problems:
            return None

        return {
            'original': original,
            'source_item': item,
            'problems': all_problems
        }

    def _check_code(self, original: str, translations: dict) -> list:
        """Программные проверки без LLM."""
        problems = []
        orig_ph = count_placeholders(original)

        for lang, text in translations.items():
            if not text.strip():
                problems.append({
                    'type': 'code_check',
                    'lang': lang,
                    'issue': 'Пустой перевод',
                    'severity': 'high'
                })
                continue

            trans_ph = count_placeholders(text)
            for ph_type, count in orig_ph.items():
                trans_count = trans_ph.get(ph_type, 0)
                if count != trans_count:
                    problems.append({
                        'type': 'code_check',
                        'lang': lang,
                        'issue': f'Плейсхолдер {ph_type}: оригинал={count}, перевод={trans_count}',
                        'severity': 'high'
                    })

            orig_len = len(original)
            trans_len = len(text)
            if orig_len > 10:
                ratio = trans_len / orig_len
                if ratio > self.max_length_ratio:
                    problems.append({
                        'type': 'code_check',
                        'lang': lang,
                        'issue': f'Подозрительно длинный перевод (x{ratio:.1f} от оригинала)',
                        'severity': 'medium'
                    })
                elif ratio < self.min_length_ratio:
                    problems.append({
                        'type': 'code_check',
                        'lang': lang,
                        'issue': f'Подозрительно короткий перевод (x{ratio:.1f} от оригинала)',
                        'severity': 'medium'
                    })

        return problems

    def _check_original_llm(self, original: str) -> list:
        """LLM-проверка русского оригинала."""
        processed = preprocess_text(original)
        prompt = ORIGINAL_CHECK_PROMPT.format(text=processed)

        try:
            raw = self.client.generate(prompt)
            items = parse_llm_json(raw)
        except Exception as e:
            logger.error(f"Ошибка LLM при проверке оригинала: {e}")
            return []

        problems = []
        for item in items:
            fix = item.get('fix', '')
            if fix:
                fix = restore_placeholders(fix, original)

            problems.append({
                'type': 'original',
                'lang': 'ru',
                'issue': item.get('issue', 'Ошибка в оригинале'),
                'severity': item.get('severity', 'medium'),
                'fix': fix
            })

        return problems

    def _check_translations_llm(self, original: str, translations: dict) -> list:
        """LLM-проверка всех переводов за один вызов."""
        trans_lines = []
        for lang, text in sorted(translations.items()):
            lang_name = LANG_NAMES.get(lang, lang)
            trans_lines.append(f'- {lang} ({lang_name}): "{text}"')
        translations_text = '\n'.join(trans_lines)

        processed_original = preprocess_text(original)
        prompt = TRANSLATION_CHECK_PROMPT.format(
            original=processed_original,
            translations=translations_text
        )

        try:
            raw = self.client.generate(prompt)
            items = parse_llm_json(raw)
        except Exception as e:
            logger.error(f"Ошибка LLM при проверке переводов: {e}")
            return []

        problems = []
        for item in items:
            lang = item.get('lang', '?')
            if lang not in translations:
                continue

            problems.append({
                'type': 'translation',
                'lang': lang,
                'issue': item.get('issue', 'Проблема с переводом'),
                'severity': item.get('severity', 'medium'),
                'fix': item.get('fix', ''),
                'current': translations.get(lang, '')
            })

        return problems
