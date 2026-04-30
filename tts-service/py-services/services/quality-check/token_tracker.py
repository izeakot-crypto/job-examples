from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Тарифы Claude ($ за 1M токенов): (input, output)
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
DEFAULT_PRICING = (5.0, 25.0)  # По умолчанию считаем как Opus 4.6


@dataclass
class LLMUsage:
    """Статистика одного вызова LLM."""
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


class TokenTracker:
    """Накапливает статистику использования токенов за сессию."""

    def __init__(self) -> None:
        self._calls: list[LLMUsage] = []

    def record(self, model: str, input_tokens: int, output_tokens: int) -> LLMUsage:
        input_rate, output_rate = PRICING.get(model, DEFAULT_PRICING)
        usage = LLMUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_tokens * input_rate / 1_000_000,
            output_cost=output_tokens * output_rate / 1_000_000,
        )
        self._calls.append(usage)
        logger.info(
            "LLM usage: in=%d, out=%d, cost=$%.6f",
            input_tokens, output_tokens, usage.total_cost,
        )
        return usage

    @property
    def total_input_tokens(self) -> int:
        return sum(u.input_tokens for u in self._calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.output_tokens for u in self._calls)

    @property
    def total_cost(self) -> float:
        return sum(u.total_cost for u in self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def summary(self) -> str:
        return (
            f"LLM итого: {self.call_count} вызовов, "
            f"input={self.total_input_tokens}, output={self.total_output_tokens}, "
            f"стоимость=${self.total_cost:.4f}"
        )
