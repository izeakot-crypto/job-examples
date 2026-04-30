from __future__ import annotations

import re

from .schemas import Sheet


# Диапазоны Unicode для определения языка
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_UKRAINIAN_RE = re.compile(r"[іїєґІЇЄҐ]")


def detect_language(text: str) -> str:
    """Определяет язык по тексту анкеты.

    - "Ukrainian" — если есть специфичные украинские буквы (і, ї, є, ґ)
    - "Russian" — кириллица без украинских букв
    - "English" — всё остальное
    """
    if _UKRAINIAN_RE.search(text):
        return "Ukrainian"
    if _CYRILLIC_RE.search(text):
        return "Russian"
    return "English"


def get_sheet_text(sheet: Sheet) -> str:
    """Собирает весь текст из анкеты для определения языка."""
    parts: list[str] = []
    for cat in sheet.value:
        parts.append(cat.title)
        for q in cat.value:
            parts.append(q.title)
            if q.desc:
                parts.append(q.desc)
    return " ".join(parts)


_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert in call center quality assurance.

You will be given a phone call transcript and a list of evaluation criteria.
For each criterion you must determine:
- "yes" — the requirement is met
- "no" — the requirement is NOT met

For each criterion you MUST provide:
1. `answer` — "yes" or "no"
2. `comment` — brief justification (1-2 sentences) explaining your decision
3. `transcript_fragment` — exact quote from the transcript supporting your decision. \
If there is no supporting quote — set null.

IMPORTANT:
- If the transcript does not confirm the requirement is met — answer "no".
- Quote the transcript VERBATIM, do not paraphrase.
- Justification must be specific, referencing facts from the conversation.
- You MUST write `comment` and `general_comment` in {language}.

Add a `general_comment` field at the end — overall assessment of the call (2-3 sentences).

Reply STRICTLY in JSON format:
{{
  "answers": [
    {{
      "category_id": <int>,
      "question_id": <int>,
      "answer": "yes" | "no",
      "comment": "<justification in {language}>",
      "transcript_fragment": "<quote>" | null
    }}
  ],
  "general_comment": "<overall assessment in {language}>"
}}

Do not add any text outside JSON.
"""


def build_system_prompt(sheet: Sheet) -> str:
    """Строит системный промпт с языком, определённым по анкете."""
    language = detect_language(get_sheet_text(sheet))
    return _SYSTEM_PROMPT_TEMPLATE.format(language=language)


def build_evaluation_prompt(sheet: Sheet, transcript_text: str) -> str:
    """Формирует user-промпт с вопросами и транскриптом."""
    questions_block = _format_questions(sheet)

    return (
        f"## Call transcript\n\n{transcript_text}\n\n"
        f"## Evaluation criteria\n\n{questions_block}\n\n"
        "Evaluate each criterion based on the transcript and return the result in JSON."
    )


def _format_questions(sheet: Sheet) -> str:
    """Извлекает вопросы из анкеты в читаемый текст."""
    lines: list[str] = []
    for category in sheet.value:
        lines.append(f"### Category {category.id}: {category.title}")
        for q in category.value:
            desc_part = f" — {q.desc}" if q.desc else ""
            lines.append(f"- [cat={category.id}, q={q.id}] {q.title}{desc_part}")
        lines.append("")
    return "\n".join(lines)
