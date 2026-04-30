from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from .config import settings
from .evaluator import EvaluationResult

logger = logging.getLogger(__name__)

AUDIT_DIR = "audit"


def _audit_dir(comp_id: int, plan_id: int) -> str:
    """Возвращает путь к директории аудита: audit/{comp_id}/{plan_id}/"""
    return os.path.join(AUDIT_DIR, str(comp_id), str(plan_id))


def _audit_filename(session_id: int) -> str:
    """Имя файла: {session_id}.json"""
    return f"{session_id}.json"


def save_audit(
    session_id: int,
    plan_id: int,
    result: EvaluationResult,
    comp_id: int | None = None,
) -> str:
    """Сохраняет полный аудит оценки в JSON-файл.

    Структура: audit/{comp_id}/{plan_id}/{session_id}.json
    Возвращает путь к созданному файлу.
    """
    if comp_id is None:
        comp_id = settings.qc_oki_toki_comp_id

    directory = _audit_dir(comp_id, plan_id)
    os.makedirs(directory, exist_ok=True)

    filename = _audit_filename(session_id)
    filepath = os.path.join(directory, filename)

    audit_data = {
        "comp_id": comp_id,
        "plan_id": plan_id,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "processing_time_ms": result.processing_time_ms,
        "llm_model": settings.llm_model,
        "llm_provider": settings.llm_provider,
        "llm_prompt": result.llm_prompt,
        "llm_response_raw": result.llm_response_raw,
        "evaluation": {
            "answers": [
                {
                    "category_id": a.category_id,
                    "question_id": a.question_id,
                    "answer": a.answer,
                    "comment": a.comment,
                    "transcript_fragment": a.transcript_fragment,
                }
                for a in result.llm_result.answers
            ],
            "general_comment": result.llm_result.general_comment,
        },
        "sheet_rating": {
            "ratings": [
                {
                    "category_id": cat.id,
                    "category_title": cat.title,
                    "questions": [
                        {"question_id": q.id, "title": q.title, "rating": q.rating}
                        for q in cat.value
                    ],
                }
                for cat in result.sheet.value
            ],
            "is_complete": result.sheet.is_complete,
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)

    logger.info("Аудит сохранён: %s", filepath)
    return filepath


def get_audit(comp_id: int, plan_id: int, session_id: int) -> dict | None:
    """Возвращает аудит-данные или None если файл не найден."""
    filepath = os.path.join(
        _audit_dir(comp_id, plan_id),
        _audit_filename(session_id),
    )
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
