"""
Простой модуль для отправки данных на webhook
"""

import requests
import logging
from typing import Any, Dict, List, Optional

# URL-адреса вебхуков
WEBHOOK_START_URL = "https://n8n.oki-toki.net/webhook/c87a2179-5d8b-418e-a68d-271b3eacbcd1"
WEBHOOK_RESULTS_URL = "https://n8n.oki-toki.net/webhook/31af2e3f-942b-4c06-b985-487cb7140e7b"

def send_webhook(url: str, data: Any, timeout: int = 10) -> bool:
    """
    Отправка данных на webhook

    Args:
        url: URL webhook'а
        data: Данные для отправки (любой JSON-сериализуемый объект)
        timeout: Таймаут запроса в секундах

    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    logger = logging.getLogger()

    try:
        response = requests.post(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )

        if response.status_code == 200:
            logger.info(f"✅ Данные успешно отправлены на webhook")
            return True
        else:
            logger.warning(f"⚠️ Webhook вернул статус: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке на webhook: {e}")
        return False