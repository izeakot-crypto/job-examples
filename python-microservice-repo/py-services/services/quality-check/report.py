"""Генератор HTML-отчётов по прогону плана проверки."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from html import escape

from .evaluator import EvaluationResult

logger = logging.getLogger(__name__)

AUDIT_DIR = "audit"

# Переводы интерфейса отчёта
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Russian": {
        "total_calls": "Всего звонков",
        "evaluated": "Оценено",
        "skipped_label": "Пропущено",
        "errors_label": "Ошибки",
        "avg_score": "Средний балл",
        "llm_cost": "Стоимость LLM",
        "tokens": "Токены (in/out)",
        "status": "Статус",
        "score": "Балл",
        "llm_time": "Время LLM",
        "details": "Детали",
        "skipped_status": "Пропущен",
        "error_status": "Ошибка",
        "evaluated_status": "Оценён",
        "show_score": "Показать оценку",
        "category": "Категория",
        "question": "Вопрос",
        "rating": "Оценка",
        "justification": "Обоснование",
        "unknown_error": "Неизвестная ошибка",
    },
    "Ukrainian": {
        "total_calls": "Всього дзвінків",
        "evaluated": "Оцінено",
        "skipped_label": "Пропущено",
        "errors_label": "Помилки",
        "avg_score": "Середній бал",
        "llm_cost": "Вартість LLM",
        "tokens": "Токени (in/out)",
        "status": "Статус",
        "score": "Бал",
        "llm_time": "Час LLM",
        "details": "Деталі",
        "skipped_status": "Пропущено",
        "error_status": "Помилка",
        "evaluated_status": "Оцінено",
        "show_score": "Показати оцінку",
        "category": "Категорія",
        "question": "Питання",
        "rating": "Оцінка",
        "justification": "Обґрунтування",
        "unknown_error": "Невідома помилка",
    },
    "English": {
        "total_calls": "Total calls",
        "evaluated": "Evaluated",
        "skipped_label": "Skipped",
        "errors_label": "Errors",
        "avg_score": "Avg score",
        "llm_cost": "LLM cost",
        "tokens": "Tokens (in/out)",
        "status": "Status",
        "score": "Score",
        "llm_time": "LLM time",
        "details": "Details",
        "skipped_status": "Skipped",
        "error_status": "Error",
        "evaluated_status": "Evaluated",
        "show_score": "Show score",
        "category": "Category",
        "question": "Question",
        "rating": "Rating",
        "justification": "Justification",
        "unknown_error": "Unknown error",
    },
}


def _get_translations(language: str) -> dict[str, str]:
    return _TRANSLATIONS.get(language, _TRANSLATIONS["English"])


@dataclass
class CallReport:
    """Данные по одному звонку для отчёта."""
    session_id: int
    status: str  # "success", "skipped", "error", "pending_transcription"
    skip_reason: str | None = None
    error_message: str | None = None
    result: EvaluationResult | None = None


@dataclass
class PlanReport:
    """Аккумулятор данных для HTML-отчёта по прогону плана."""
    comp_id: int
    plan_id: int
    plan_name: str = ""
    language: str = "Russian"
    started_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    calls: list[CallReport] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_calls: int = 0

    def add_call(self, report: CallReport) -> None:
        self.calls.append(report)

    @property
    def success_count(self) -> int:
        return sum(1 for c in self.calls if c.status == "success")

    @property
    def skipped_count(self) -> int:
        return sum(1 for c in self.calls if c.status == "skipped")

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.calls if c.status == "error")


def generate_html_report(report: PlanReport) -> str:
    """Генерирует HTML-отчёт и сохраняет в файл. Возвращает путь."""
    html = _build_html(report)

    report_dir = os.path.join(AUDIT_DIR, str(report.comp_id), str(report.plan_id))
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_comp{report.comp_id}_plan{report.plan_id}_{timestamp}.html"
    filepath = os.path.join(report_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("HTML-отчёт сохранён: %s", filepath)
    _cleanup_old_reports()
    return filepath


REPORT_TTL_DAYS = 30


def _cleanup_old_reports() -> None:
    """Удаляет все файлы в audit/ старше REPORT_TTL_DAYS дней (html + json)."""
    import time

    if not os.path.exists(AUDIT_DIR):
        return

    cutoff = time.time() - REPORT_TTL_DAYS * 86400
    removed = 0
    for root, dirs, files in os.walk(AUDIT_DIR):
        for f in files:
            path = os.path.join(root, f)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
    # Удаляем пустые директории
    for root, dirs, files in os.walk(AUDIT_DIR, topdown=False):
        if root != AUDIT_DIR and not os.listdir(root):
            os.rmdir(root)
    if removed:
        logger.info("Удалено файлов старше %d дней: %d", REPORT_TTL_DAYS, removed)


def _build_html(report: PlanReport) -> str:
    t = _get_translations(report.language)
    lang_code = {"Russian": "ru", "Ukrainian": "uk"}.get(report.language, "en")

    total = len(report.calls)
    success = report.success_count
    skipped = report.skipped_count
    errors = report.error_count

    total_rating = 0
    max_rating = 0
    for c in report.calls:
        if c.status == "success" and c.result:
            for cat in c.result.sheet.value:
                for q in cat.value:
                    if q.rating is not None:
                        total_rating += q.rating
                        max_rating += 1

    rating_pct = (total_rating / max_rating * 100) if max_rating > 0 else 0

    call_rows = []
    for c in report.calls:
        call_rows.append(_build_call_row(c, t))

    return f"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
<meta charset="utf-8">
<title>{escape(report.plan_name or f'Plan {report.plan_id}')}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 20px; color: #1a1a2e; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card .label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
  .card .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
  .card .value.green {{ color: #16a34a; }}
  .card .value.orange {{ color: #ea580c; }}
  .card .value.red {{ color: #dc2626; }}
  .card .value.blue {{ color: #2563eb; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th {{ background: #1a1a2e; color: #fff; padding: 10px 14px; text-align: left; font-size: 13px; font-weight: 600; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #eee; font-size: 13px; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .status-success {{ color: #16a34a; font-weight: 600; }}
  .status-skipped {{ color: #ea580c; font-weight: 600; }}
  .status-error {{ color: #dc2626; font-weight: 600; }}
  .badge-yes {{ background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .badge-no {{ background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  details {{ margin-bottom: 2px; }}
  details summary {{ cursor: pointer; padding: 6px 0; font-size: 13px; }}
  details summary:hover {{ color: #2563eb; }}
  .detail-table {{ width: 100%; margin: 8px 0 12px 0; }}
  .detail-table th {{ background: #f1f5f9; color: #333; font-size: 12px; padding: 6px 10px; }}
  .detail-table td {{ font-size: 12px; padding: 6px 10px; }}
  .comment {{ color: #555; font-style: italic; font-size: 12px; margin-top: 8px; padding: 8px 12px; background: #f9fafb; border-left: 3px solid #2563eb; border-radius: 0 4px 4px 0; }}
  .fragment {{ color: #666; font-size: 11px; }}
  .meta {{ font-size: 12px; color: #888; margin-bottom: 16px; }}
</style>
</head>
<body>
<div class="container">
  <h1>{escape(report.plan_name or f'Plan {report.plan_id}')}</h1>
  <div class="meta">
    comp_id: {report.comp_id} &bull; plan_id: {report.plan_id} &bull; {report.started_at}
  </div>

  <div class="summary">
    <div class="card"><div class="label">{t['total_calls']}</div><div class="value blue">{total}</div></div>
    <div class="card"><div class="label">{t['evaluated']}</div><div class="value green">{success}</div></div>
    <div class="card"><div class="label">{t['skipped_label']}</div><div class="value orange">{skipped}</div></div>
    <div class="card"><div class="label">{t['errors_label']}</div><div class="value red">{errors}</div></div>
    <div class="card"><div class="label">{t['avg_score']}</div><div class="value">{rating_pct:.0f}%</div></div>
    <div class="card"><div class="label">{t['llm_cost']}</div><div class="value">${report.total_cost:.4f}</div></div>
    <div class="card"><div class="label">{t['tokens']}</div><div class="value" style="font-size:16px">{report.total_input_tokens:,} / {report.total_output_tokens:,}</div></div>
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:50px">#</th>
        <th>Session ID</th>
        <th>{t['status']}</th>
        <th>{t['score']}</th>
        <th>{t['llm_time']}</th>
        <th>{t['details']}</th>
      </tr>
    </thead>
    <tbody>
      {''.join(call_rows)}
    </tbody>
  </table>
</div>
</body>
</html>"""


def _build_call_row(c: CallReport, t: dict[str, str]) -> str:
    sid = c.session_id

    if c.status == "skipped":
        reason = escape(c.skip_reason or "—")
        return f"""<tr>
  <td></td>
  <td>{sid}</td>
  <td class="status-skipped">{t['skipped_status']}</td>
  <td>—</td>
  <td>—</td>
  <td>{reason}</td>
</tr>"""

    if c.status == "error":
        err = escape(c.error_message or t['unknown_error'])
        return f"""<tr>
  <td></td>
  <td>{sid}</td>
  <td class="status-error">{t['error_status']}</td>
  <td>—</td>
  <td>—</td>
  <td>{err}</td>
</tr>"""

    r = c.result
    if not r:
        return ""

    yes_count = sum(1 for cat in r.sheet.value for q in cat.value if q.rating == 1)
    total_q = sum(1 for cat in r.sheet.value for q in cat.value)
    score = f"{yes_count}/{total_q}"
    time_s = f"{r.processing_time_ms / 1000:.1f}s"

    # Определяем язык по уникальным ключам перевода
    if t["evaluated"] == "Оценено":
        badge_yes, badge_no = "Да", "Нет"
    elif t["evaluated"] == "Оцінено":
        badge_yes, badge_no = "Так", "Ні"
    else:
        badge_yes, badge_no = "Yes", "No"

    detail_rows = []
    for cat in r.sheet.value:
        cat_title = escape(cat.title)
        for q in cat.value:
            q_title = escape(q.title)
            badge = f'<span class="badge-yes">{badge_yes}</span>' if q.rating == 1 else f'<span class="badge-no">{badge_no}</span>'

            comment = ""
            fragment = ""
            for a in r.llm_result.answers:
                if a.category_id == cat.id and a.question_id == q.id:
                    if a.comment:
                        comment = escape(a.comment)
                    if a.transcript_fragment:
                        fragment = f'<div class="fragment">«{escape(a.transcript_fragment)}»</div>'
                    break

            detail_rows.append(
                f"<tr><td>{cat_title}</td><td>{q_title}</td><td>{badge}</td>"
                f"<td>{comment}{fragment}</td></tr>"
            )

    general = ""
    if r.llm_result.general_comment:
        general = f'<div class="comment">{escape(r.llm_result.general_comment)}</div>'

    details_html = f"""<details>
  <summary>{t['show_score']} ({score})</summary>
  <table class="detail-table">
    <thead><tr><th>{t['category']}</th><th>{t['question']}</th><th>{t['rating']}</th><th>{t['justification']}</th></tr></thead>
    <tbody>{''.join(detail_rows)}</tbody>
  </table>
  {general}
</details>"""

    return f"""<tr>
  <td></td>
  <td>{sid}</td>
  <td class="status-success">{t['evaluated_status']}</td>
  <td>{score}</td>
  <td>{time_s}</td>
  <td>{details_html}</td>
</tr>"""
