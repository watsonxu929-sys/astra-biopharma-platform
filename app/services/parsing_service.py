from __future__ import annotations

from typing import Any

from app.services.parsers import DocumentParser, HtmlParser, ParseResult, TextParser, UnsupportedContentType


class ParsingService:
    def __init__(self, parsers=None):
        self.parsers = list(parsers or [HtmlParser(), TextParser(), DocumentParser()])

    def parse(self, snapshot: dict[str, Any]) -> ParseResult:
        content_type = str(snapshot.get("content_type") or "text/html")
        for parser in self.parsers:
            if parser.supports(content_type):
                return parser.parse(snapshot)
        raise UnsupportedContentType(f"unsupported_content_type:{content_type}")
