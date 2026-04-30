#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты обработки текста: предобработка, восстановление плейсхолдеров и кавычек.
"""
import re

# Все виды кавычек, которые LLM может подменять
_ALL_QUOTE_CHARS = set('"\'\u00AB\u00BB\u2018\u2019\u201C\u201D\u201E\u2039\u203A')


def preprocess_text(text: str) -> str:
    """Подготовка текста к проверке — убираем шум для LLM."""
    processed = text.replace('%s', '[PLACEHOLDER]')
    processed = processed.replace('%d', '[NUMBER]')
    processed = processed.replace('%1$s', '[PLACEHOLDER]')
    processed = processed.replace('%2$s', '[PLACEHOLDER]')
    processed = re.sub(r'\{\{.*?\}\}', '[TEMPLATE]', processed)
    processed = re.sub(r'<[^>]+>', '', processed)
    return processed.strip()


def restore_placeholders(suggestion: str, original: str) -> str:
    """Восстанавливает оригинальные переменные/плейсхолдеры в suggestion от LLM."""
    templates = re.findall(r'\{\{.*?\}\}', original)
    placeholders = []
    for m in re.finditer(r'%(?:\d+\$)?s', original):
        placeholders.append(m.group())
    numbers = []
    for m in re.finditer(r'%(?:\d+\$)?d', original):
        numbers.append(m.group())

    result = suggestion

    for tpl in templates:
        result = result.replace('[TEMPLATE]', tpl, 1)
    for ph in placeholders:
        result = result.replace('[PLACEHOLDER]', ph, 1)
    for num in numbers:
        result = result.replace('[NUMBER]', num, 1)

    result = result.replace('[TEMPLATE]', '')
    result = result.replace('[PLACEHOLDER]', '')
    result = result.replace('[NUMBER]', '')
    result = re.sub(r'\s{2,}', ' ', result).strip()

    result = restore_quotes(result, original)
    return result


def restore_quotes(suggestion: str, original: str) -> str:
    """Восстанавливает ТОЧНЫЕ кавычки из оригинала в suggestion."""
    orig_quotes = [c for c in original if c in _ALL_QUOTE_CHARS]
    if not orig_quotes:
        return suggestion

    sugg_quotes = [c for c in suggestion if c in _ALL_QUOTE_CHARS]
    if not sugg_quotes:
        return suggestion

    if len(orig_quotes) == len(sugg_quotes):
        if orig_quotes == sugg_quotes:
            return suggestion
        result = []
        q_idx = 0
        for ch in suggestion:
            if ch in _ALL_QUOTE_CHARS:
                result.append(orig_quotes[q_idx])
                q_idx += 1
            else:
                result.append(ch)
        return ''.join(result)

    result = []
    q_idx = 0
    for ch in suggestion:
        if ch in _ALL_QUOTE_CHARS and q_idx < len(orig_quotes):
            result.append(orig_quotes[q_idx])
            q_idx += 1
        else:
            result.append(ch)
    return ''.join(result)


def count_placeholders(text: str) -> dict:
    """Подсчитывает количество плейсхолдеров в тексте."""
    return {
        '%s': len(re.findall(r'%(?:\d+\$)?s', text)),
        '%d': len(re.findall(r'%(?:\d+\$)?d', text)),
        '{{}}': len(re.findall(r'\{\{.*?\}\}', text)),
    }


def count_quotes(text: str) -> dict:
    """Подсчитывает типы кавычек в тексте."""
    counts = {}
    for ch in text:
        if ch in _ALL_QUOTE_CHARS:
            counts[ch] = counts.get(ch, 0) + 1
    return counts
