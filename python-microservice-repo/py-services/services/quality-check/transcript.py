from __future__ import annotations

from .schemas import Transcript

# Маппинг каналов транскрипции Оки-Токи
CHANNEL_LABELS = {
    1: "Клиент",
    2: "Оператор",
}


def format_transcript(transcript: Transcript) -> str:
    """Форматирует транскрипт в текст для промпта LLM.

    Формат:
        [Оператор] (0:06 - 0:11): текст реплики
        [Клиент] (0:12 - 0:15): текст реплики
    """
    if not transcript.items:
        return ""

    lines: list[str] = []
    for item in transcript.items:
        start = _format_time(item.start_time)
        end = _format_time(item.end_time)
        label = CHANNEL_LABELS.get(item.channel, f"Канал {item.channel}")
        lines.append(f"[{label}] ({start} - {end}): {item.text}")

    return "\n".join(lines)


def _format_time(seconds: float) -> str:
    """Преобразует секунды в формат M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"
