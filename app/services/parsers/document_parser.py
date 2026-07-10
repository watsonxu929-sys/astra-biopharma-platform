from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .base import Citation, ParseResult, ParserUnavailable


class DocumentParser:
    name = "docling_optional_v1"
    supported_types = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("docling") is not None

    def supports(self, content_type: str) -> bool:
        return (content_type or "").lower().split(";", 1)[0] in self.supported_types

    def _require(self) -> None:
        if not self.available:
            raise ParserUnavailable("docling_parser_unavailable")

    def extract_metadata(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self._require()
        return {"attachment_path": snapshot.get("attachment_path")}

    def extract_text(self, snapshot: dict[str, Any]) -> str:
        self._require()
        path = Path(str(snapshot.get("attachment_path") or ""))
        if not path.exists():
            raise ParserUnavailable("document_attachment_unavailable")
        from docling.document_converter import DocumentConverter
        result = DocumentConverter().convert(str(path))
        return result.document.export_to_markdown()

    def extract_sections(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def extract_tables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def build_citations(self, text: str) -> list[Citation]:
        return [Citation(excerpt=text[:500], char_start=0, char_end=min(len(text), 500), locator={"adapter": self.name})] if text else []

    def parse(self, snapshot: dict[str, Any]) -> ParseResult:
        text = self.extract_text(snapshot)
        return ParseResult(text=text, metadata=self.extract_metadata(snapshot), citations=self.build_citations(text), parser_name=self.name)
