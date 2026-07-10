from __future__ import annotations

import re
from typing import Any

from .base import Citation, ParseResult


class TextParser:
    name = "plain_text_v1"

    def supports(self, content_type: str) -> bool:
        value = (content_type or "").lower()
        return value.startswith("text/plain") or value in {"text", "plain"}

    def extract_metadata(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {"title": snapshot.get("page_title") or ""}

    def extract_text(self, snapshot: dict[str, Any]) -> str:
        return re.sub(r"[ \t]+", " ", str(snapshot.get("raw_content") or snapshot.get("cleaned_text") or "")).strip()

    def extract_sections(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def extract_tables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def build_citations(self, text: str) -> list[Citation]:
        return [Citation(excerpt=text[:500], char_start=0, char_end=min(len(text), 500))] if text else []

    def parse(self, snapshot: dict[str, Any]) -> ParseResult:
        text = self.extract_text(snapshot)
        return ParseResult(text=text, metadata=self.extract_metadata(snapshot), citations=self.build_citations(text), parser_name=self.name)
