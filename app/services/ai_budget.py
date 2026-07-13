from __future__ import annotations

from dataclasses import dataclass


class AIBudgetExceeded(RuntimeError):
    pass


@dataclass
class AIPilotBudget:
    max_calls: int = 20
    max_cost_usd: float = 5.0
    calls: int = 0
    estimated_cost_usd: float = 0.0

    def reserve(self, provider_name: str) -> None:
        if provider_name != "openai":
            return
        if self.calls >= min(self.max_calls, 20):
            raise AIBudgetExceeded("ai_call_limit_exceeded")
        if self.estimated_cost_usd >= self.max_cost_usd:
            raise AIBudgetExceeded("ai_budget_exceeded")
        self.calls += 1

    def record_usage(
        self,
        usage: dict,
        *,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
    ) -> float:
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        cost = input_tokens * input_cost_per_million / 1_000_000
        cost += output_tokens * output_cost_per_million / 1_000_000
        self.estimated_cost_usd += cost
        return cost
