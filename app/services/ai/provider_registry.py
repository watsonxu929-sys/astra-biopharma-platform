from __future__ import annotations

from .base import AIProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider
from .rule_provider import RuleProvider


class ProviderRegistry:
    def __init__(self, providers: dict[str, AIProvider] | None = None):
        self.providers = providers or {"rule": RuleProvider(), "mock": MockProvider(), "openai": OpenAIProvider()}

    def get(self, name: str = "rule", *, fallback: bool = True) -> AIProvider:
        provider = self.providers.get(name)
        if provider and provider.available:
            return provider
        if fallback:
            return self.providers["rule"]
        raise LookupError(f"provider_unavailable:{name}")
