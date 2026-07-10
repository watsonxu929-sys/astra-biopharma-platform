from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class UnsupportedContentType(ValueError):
    pass


class ParserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Citation:
    excerpt: str
    char_start: int | None = None
    char_end: int | None = None
    page_number: int | None = None
    table_number: str | None = None
    locator: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    parser_name: str = ""
    status: str = "success"


class ContentParser(Protocol):
    def supports(self, content_type: str) -> bool: ...
    def parse(self, snapshot: dict[str, Any]) -> ParseResult: ...
    def extract_metadata(self, snapshot: dict[str, Any]) -> dict[str, Any]: ...
    def extract_text(self, snapshot: dict[str, Any]) -> str: ...
    def extract_sections(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]: ...
    def extract_tables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]: ...
    def build_citations(self, text: str) -> list[Citation]: ...
