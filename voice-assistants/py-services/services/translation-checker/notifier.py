#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отправка алертов в Telegram и Discord для translation-checker.
"""
import json
import os
import socket
import time

import requests

from shared.logger import get_logger

logger = get_logger("translation-checker.notifier")

# Динамически определяем информацию о сервере
_SCRIPT_PATH = os.environ.get('HOST_SCRIPT_PATH', os.path.abspath(__file__))


def _get_hostname() -> str:
    """Определяет hostname хоста: из прокинутого файла, env или socket."""
    host_file = '/etc/host_hostname'
    if os.path.exists(host_file):
        with open(host_file, 'r') as f:
            name = f.read().strip()
            if name:
                return name
    return os.environ.get('HOST_HOSTNAME', socket.getfqdn())


_HOSTNAME = _get_hostname()

LANG_NAMES = {
    'ru': 'Русский',
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

MAX_RETRIES = 3


def escape_html(text: str) -> str:
    """Экранирование HTML для Telegram."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def _build_problems_data(result: dict) -> tuple:
    """Подготавливает данные проблем из результата анализа."""
    problems = result.get('problems', [])
    source_item = result.get('source_item', {})
    if not problems:
        return None, None
    return source_item, problems


class TelegramNotifier:
    """Отправка алертов через Telegram Bot API с retry."""

    def __init__(self, bot_token: str, chat_id: int):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send_alert(self, result: dict):
        """Отправляет алерт о проблемах с переводом."""
        source_item, problems = _build_problems_data(result)
        if not problems:
            return

        lines = ['<b>Проблема с переводом</b>', '']

        json_str = json.dumps(source_item, ensure_ascii=False, indent=2)
        if len(json_str) > 2500:
            json_str = json_str[:2500] + '\n  ...'
        lines.append(f'<pre>{escape_html(json_str)}</pre>')
        lines.append('')
        lines.append('<b>Проблемы:</b>')

        for p in problems:
            lang = p.get('lang', '?')
            if p['type'] == 'original':
                lines.append(f'<b>Оригинал:</b> {escape_html(p["issue"])}')
                if p.get('fix'):
                    lines.append(f'   -> {escape_html(p["fix"][:200])}')
            elif p['type'] == 'code_check':
                lines.append(f'<b>{lang}:</b> {escape_html(p["issue"])}')
            elif p['type'] == 'translation':
                lines.append(f'<b>{lang}:</b> {escape_html(p["issue"])}')
                if p.get('fix'):
                    lines.append(f'   -> {escape_html(p["fix"][:200])}')

        message = '\n'.join(lines)
        if len(message) > 4000:
            message = message[:3990] + '\n\n...(обрезано)'

        self._send_message(message)

    def _send_message(self, text: str):
        """Отправка сообщения через Bot API с retry при rate limit."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': text,
                        'parse_mode': 'HTML',
                        'disable_web_page_preview': True
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    logger.info(f"Алерт отправлен в Telegram (чат {self.chat_id})")
                    return
                elif resp.status_code == 429:
                    retry_after = resp.json().get('parameters', {}).get('retry_after', 5)
                    logger.warning(f"Telegram rate limit, жду {retry_after}с (попытка {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"Ошибка отправки в Telegram: HTTP {resp.status_code} | {resp.text[:200]}")
                    return
            except requests.exceptions.Timeout:
                logger.warning(f"Telegram таймаут (попытка {attempt + 1}/{MAX_RETRIES})")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Ошибка отправки в Telegram: {e}")
                return

        logger.error("Не удалось отправить алерт в Telegram после всех попыток")


class DiscordNotifier:
    """Отправка алертов через Discord Webhook с embeds."""

    COLOR_WARNING = 0xFFA500
    COLOR_ERROR = 0xFF0000

    def __init__(self, webhook_url: str, username: str = 'Translation Monitor'):
        self.webhook_url = webhook_url
        self.username = username

    def send_alert(self, result: dict):
        """Отправляет алерт о проблемах с переводом в Discord через embed."""
        source_item, problems = _build_problems_data(result)
        if not problems:
            return

        has_high = any(p.get('severity') == 'high' for p in problems)
        color = self.COLOR_ERROR if has_high else self.COLOR_WARNING

        json_str = json.dumps(source_item, ensure_ascii=False, indent=2)
        if len(json_str) > 3500:
            json_str = json_str[:3500] + '\n  ...'
        description = f"```json\n{json_str}\n```"

        fields = []
        for p in problems:
            lang = p.get('lang', '?')
            name = 'Оригинал' if p['type'] == 'original' else lang
            value = p.get('issue', '')
            if p.get('fix'):
                value += f"\n-> {p['fix'][:200]}"
            fields.append({
                'name': name,
                'value': value[:1024],
                'inline': False
            })

        if len(fields) > 23:
            fields = fields[:22]
            fields.append({
                'name': f'... и ещё {len(problems) - 22}',
                'value': 'Слишком много проблем для отображения',
                'inline': False
            })

        fields.append({'name': 'Sender script name', 'value': _SCRIPT_PATH, 'inline': False})
        fields.append({'name': 'Server', 'value': _HOSTNAME, 'inline': False})

        embed = {
            'title': 'Проблема с переводом',
            'description': description,
            'color': color,
            'fields': fields,
        }

        self._send({'username': self.username, 'embeds': [embed]})

    def _send(self, data: dict):
        """Отправка данных через Discord Webhook с retry."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(self.webhook_url, json=data, timeout=30)
                if resp.status_code in (200, 204):
                    logger.info("Алерт отправлен в Discord")
                    return
                elif resp.status_code == 429:
                    retry_after = resp.json().get('retry_after', 5)
                    logger.warning(f"Discord rate limit, жду {retry_after}с (попытка {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_after)
                    continue
                else:
                    logger.error(f"Ошибка отправки в Discord: HTTP {resp.status_code} | {resp.text[:200]}")
                    return
            except requests.exceptions.Timeout:
                logger.warning(f"Discord таймаут (попытка {attempt + 1}/{MAX_RETRIES})")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Ошибка отправки в Discord: {e}")
                return

        logger.error("Не удалось отправить алерт в Discord после всех попыток")
