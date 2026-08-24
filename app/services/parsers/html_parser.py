from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.core.content_extraction import extract_main_text
from .base import Citation, ParseResult


class HtmlParser:
    name = "trafilatura_html_v1"

    def supports(self, content_type: str) -> bool:
        return "html" in (content_type or "").lower()

    def extract_metadata(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        soup = BeautifulSoup(snapshot.get("raw_html") or snapshot.get("raw_content") or "", "html.parser")
        description = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        return {"title": (soup.title.string.strip() if soup.title and soup.title.string else snapshot.get("page_title") or ""), "description": description.get("content", "").strip() if description else ""}

    def extract_text(self, snapshot: dict[str, Any]) -> str:
        text, _ = extract_main_text(snapshot.get("raw_html") or snapshot.get("raw_content") or "")
        return text

    def extract_sections(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        soup = BeautifulSoup(snapshot.get("raw_html") or snapshot.get("raw_content") or "", "html.parser")
        return [{"heading": node.get_text(" ", strip=True), "level": node.name} for node in soup.find_all(["h1", "h2", "h3"]) if node.get_text(strip=True)]

    def extract_tables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        soup = BeautifulSoup(snapshot.get("raw_html") or snapshot.get("raw_content") or "", "html.parser")
        tables = []
        for index, table in enumerate(soup.find_all("table"), 1):
            rows = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])] for row in table.find_all("tr")]
            tables.append({"table_number": str(index), "rows": [row for row in rows if row]})
        return tables

    def build_citations(self, text: str) -> list[Citation]:
        if not text:
            return []
        return [Citation(excerpt=text[:500], char_start=0, char_end=min(len(text), 500), locator={"parser": self.name})]

    def parse(self, snapshot: dict[str, Any]) -> ParseResult:
        text = self.extract_text(snapshot)
        return ParseResult(text=text, metadata=self.extract_metadata(snapshot), sections=self.extract_sections(snapshot), tables=self.extract_tables(snapshot), citations=self.build_citations(text), parser_name=self.name)
