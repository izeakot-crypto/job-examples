"""Основная бизнес-логика: полный цикл проверки плана."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from .config import settings
from .oki_toki import OkiTokiClient
from .evaluator import Evaluator
from .audit import save_audit
from .prompts import detect_language, get_sheet_text
from .report import CallReport, PlanReport, generate_html_report
from .transcript import format_transcript

logger = logging.getLogger(__name__)


@dataclass
class RunProgress:
    """Прогресс выполнения проверки плана."""
    total: int = 0
    processed: int = 0
    success: int = 0
    skipped: int = 0
    errors: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "processed": self.processed,
            "success": self.success,
            "skipped": self.skipped,
            "errors": self.errors,
        }


_SKIP_REASONS: dict[str, dict[str, str]] = {
    "Russian": {
        "no_transcript": "Нечего распознавать: транскрипция отсутствует",
        "short_call": "Нечего распознавать: звонок слишком короткий ({duration:.1f}с)",
        "error": "Ошибка автоматической проверки: {error}",
    },
    "Ukrainian": {
        "no_transcript": "Нема що розпізнавати: транскрипція відсутня",
        "short_call": "Нема що розпізнавати: дзвінок занадто короткий ({duration:.1f}с)",
        "error": "Помилка автоматичної перевірки: {error}",
    },
    "English": {
        "no_transcript": "Nothing to recognize: transcript is missing",
        "short_call": "Nothing to recognize: call too short ({duration:.1f}s)",
        "error": "Automatic check error: {error}",
    },
}


async def process_call(
    client: OkiTokiClient,
    evaluator: Evaluator,
    semaphore: asyncio.Semaphore,
    comp_id: int,
    plan_id: int,
    session_id: int,
    progress: RunProgress,
    language: str = "Russian",
) -> CallReport:
    """Обрабатывает один звонок. Возвращает CallReport."""
    logger.info("Обработка звонка session_id=%d", session_id)
    reasons = _SKIP_REASONS.get(language, _SKIP_REASONS["English"])

    try:
        sheet = await client.get_call_sheet(plan_id, session_id)
        transcript = await client.get_transcript(session_id)
        has_transcript = transcript.done and len(transcript.items) > 0

        if not has_transcript:
            reason = reasons["no_transcript"]
            logger.warning("Транскрипт session_id=%d отсутствует — пропускаем", session_id)
            await client.skip_call_sheet(plan_id, session_id, reason)
            progress.skipped += 1
            progress.processed += 1
            return CallReport(session_id=session_id, status="skipped", skip_reason=reason)

        total_duration = max(item.end_time for item in transcript.items)
        if total_duration < settings.qc_skip_short_calls_sec:
            reason = reasons["short_call"].format(duration=total_duration)
            logger.info(
                "Звонок session_id=%d слишком короткий (%.1f сек), пропускаем",
                session_id, total_duration,
            )
            await client.skip_call_sheet(plan_id, session_id, reason)
            progress.skipped += 1
            progress.processed += 1
            return CallReport(session_id=session_id, status="skipped", skip_reason=reason)

        transcript_text = format_transcript(transcript)

        async with semaphore:
            logger.debug("session_id=%d — слот LLM получен", session_id)
            result = await evaluator.evaluate(sheet, transcript_text)

        llm = result.llm_result
        logger.info("session_id=%d | LLM оценка (%d ms):", session_id, result.processing_time_ms)
        for a in llm.answers:
            logger.info(
                "  [cat=%d q=%d] %s | %s | fragment: %s",
                a.category_id, a.question_id, a.answer.upper(),
                a.comment or "-",
                (a.transcript_fragment[:60] + "...") if a.transcript_fragment and len(a.transcript_fragment) > 60 else (a.transcript_fragment or "-"),
            )
        if llm.general_comment:
            logger.info("  Общий вывод: %s", llm.general_comment)

        save_audit(session_id, plan_id, result, comp_id=comp_id)

        await client.save_call_sheet(session_id, result.sheet)
        logger.info("session_id=%d — анкета сохранена", session_id)
        progress.success += 1
        progress.processed += 1
        return CallReport(session_id=session_id, status="success", result=result)

    except Exception as exc:
        logger.exception("Ошибка при обработке session_id=%d", session_id)
        try:
            await client.skip_call_sheet(
                plan_id, session_id,
                reasons["error"].format(error=str(exc)[:200]),
            )
            logger.info("session_id=%d — пропущена после ошибки", session_id)
        except Exception:
            logger.exception("Не удалось пропустить session_id=%d после ошибки", session_id)
        progress.errors += 1
        progress.processed += 1
        return CallReport(session_id=session_id, status="error", error_message=str(exc))


async def run_plan(
    plan_id: int,
    comp_id: int | None = None,
    progress: RunProgress | None = None,
) -> dict:
    """Запускает полный цикл проверки плана. Возвращает статистику."""
    if comp_id is None:
        comp_id = settings.qc_oki_toki_comp_id
    if progress is None:
        progress = RunProgress()

    async with OkiTokiClient(comp_id=comp_id) as client:
        plan = await client.get_plan(plan_id)
        logger.info("План: %s (comp_id=%d, template_id=%d)", plan.name, comp_id, plan.template_parent_id)

        sessions = await client.get_unchecked_sessions(plan_id)
        logger.info("Непроверенных звонков: %d", len(sessions))

        if not sessions:
            logger.info("Нет звонков для проверки")
            return {"success": 0, "skipped": 0, "errors": 0, "total": 0, "cost": "$0.0000"}

        progress.total = len(sessions)

        evaluator = Evaluator()
        semaphore = asyncio.Semaphore(settings.qc_max_concurrent_llm)

        # Определяем язык по первой анкете
        first_sheet = await client.get_call_sheet(plan_id, sessions[0])
        language = detect_language(get_sheet_text(first_sheet))
        logger.info("Определён язык анкеты: %s", language)

        plan_report = PlanReport(
            comp_id=comp_id,
            plan_id=plan_id,
            plan_name=plan.name,
            language=language,
        )

        tasks = [
            process_call(client, evaluator, semaphore, comp_id, plan_id, sid, progress, language)
            for sid in sessions
        ]
        call_reports = await asyncio.gather(*tasks)

        for cr in call_reports:
            plan_report.add_call(cr)

        plan_report.total_cost = evaluator.tracker.total_cost
        plan_report.total_input_tokens = evaluator.tracker.total_input_tokens
        plan_report.total_output_tokens = evaluator.tracker.total_output_tokens
        plan_report.llm_calls = evaluator.tracker.call_count

        report_path = generate_html_report(plan_report)

        cost_summary = evaluator.tracker.summary()
        logger.info(
            "Готово. Успешно: %d, пропущено: %d, ошибок: %d, всего: %d",
            progress.success, progress.skipped, progress.errors, progress.total,
        )
        logger.info(cost_summary)
        logger.info("HTML-отчёт: %s", report_path)

        await evaluator.close()

        return {
            "success": progress.success,
            "skipped": progress.skipped,
            "errors": progress.errors,
            "total": progress.total,
            "cost": f"${evaluator.tracker.total_cost:.4f}",
            "tokens": {
                "input": evaluator.tracker.total_input_tokens,
                "output": evaluator.tracker.total_output_tokens,
            },
            "llm_calls": evaluator.tracker.call_count,
            "report": report_path,
        }
