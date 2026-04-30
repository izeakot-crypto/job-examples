from __future__ import annotations

from pydantic import BaseModel


# --- План проверки ---

class PlanFilter(BaseModel):
    count_calls: int = 0
    method_check: int = 1
    link_calls_log: str = ""
    phones_lists_ids: list = []
    api_session_ids: list = []
    is_random: bool = False
    is_deform: bool = False


class PlanLimits(BaseModel):
    dtimeFrom: str | None = None
    dtimeTo: str | None = None


class Plan(BaseModel):
    id: int
    name: str
    desc: str = ""
    author_id: int = 0
    project_id: int = 0
    template_parent_id: int
    users_checkers: list[int] = []
    deleted: bool = False
    filter: PlanFilter = PlanFilter()
    limits: PlanLimits = PlanLimits()
    dtime: str = ""
    count_full_sheets: int = 0


# --- Шаблон оценочного листа ---

class TemplateQuestion(BaseModel):
    id: int
    title: str
    desc: str = ""
    factor: float | None = None


class TemplateCategory(BaseModel):
    id: int
    title: str
    factor: float = 1
    value: list[TemplateQuestion] = []


class Template(BaseModel):
    id: int
    parent_id: int = 0
    name: str
    desc: str = ""
    author_id: int = 0
    author_name: str = ""
    dtime: str = ""
    value: list[TemplateCategory] = []


# --- Анкета (call/get и call/set) ---

class SheetQuestion(BaseModel):
    id: int
    title: str
    desc: str = ""
    factor: float | None = None
    rating: int | None = None


class SheetCategory(BaseModel):
    id: int
    title: str
    factor: float = 1
    value: list[SheetQuestion] = []


class Sheet(BaseModel):
    id: int
    name: str = ""
    desc: str = ""
    is_used: bool = True
    template_parent_id: int = 0
    count_demand: int = 0
    rating_max: int = 0
    sheet_id: int = 0
    plan_id: int = 0
    sheet_dtime: str | None = None
    author: str | None = None
    is_call_attention: bool = False
    comment: str | None = None
    comment_other: str | None = None
    is_started: bool = False
    is_complete: bool = False
    rating: int | None = None
    rating_left: int | None = None
    link_delete: str | None = None
    is_permission_delete: bool = False
    is_permission_save: bool = True
    value: list[SheetCategory] = []


# --- Ответ LLM (расширенный) ---

class LLMAnswer(BaseModel):
    """Один ответ LLM на вопрос анкеты."""
    category_id: int
    question_id: int
    answer: str  # "yes" | "no"
    comment: str | None = None
    transcript_fragment: str | None = None


class LLMResult(BaseModel):
    """Полный ответ LLM по всей анкете."""
    answers: list[LLMAnswer]
    general_comment: str | None = None


# --- Транскрипт ---

class TranscriptItem(BaseModel):
    text: str
    channel: int
    start_time: float
    end_time: float


class Transcript(BaseModel):
    done: bool
    items: list[TranscriptItem] = []
