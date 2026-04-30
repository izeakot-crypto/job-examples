#!/usr/bin/env python3
"""
Клієнт до Whisper API для транскрипції аудіо.
"""
import httpx

from shared.logger import get_logger

logger = get_logger("transcribe")


class WhisperClient:
    """HTTP клієнт до Parakeet ASR API (Макс)."""

    def __init__(self, url: str, model: str, connect_timeout: float = 10, timeout: float = 800):
        self.url = url.rstrip("/") + "/parakeet_asr"
        self.model = model
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    async def transcribe(self, audio_data: bytes, filename: str, locale: str) -> list[dict]:
        """Відправляє аудіо на Parakeet ASR API, повертає список сегментів.

        Args:
            audio_data: Бінарні дані аудіофайлу.
            filename: Ім'я файлу (потрібне для multipart).
            locale: Мова (наприклад 'uk', 'ru', 'en').

        Returns:
            Список сегментів:
            [{"channel": 1, "start_time": 1.23, "end_time": 2.45, "text": "привіт"}, ...]
        """
        lang = locale.split("_")[0].split("-")[0]

        files = {"file": (filename, audio_data, "audio/mpeg")}
        data = {
            "model": self.model,
            "response_format": "verbose_json",
            "pause_threshold": "1.5",
        }
        if lang:
            data["language"] = lang

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, files=files, data=data)
            response.raise_for_status()

        result = response.json()
        segments = result.get("segments", [])

        items = []
        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue
            items.append({
                "channel": 1,
                "start_time": round(float(seg.get("start", 0)), 2),
                "end_time": round(float(seg.get("end", 0)), 2),
                "text": text,
            })

        return items
