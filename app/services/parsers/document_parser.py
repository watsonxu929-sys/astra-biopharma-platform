from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .base import Citation, ParseResult, ParserUnavailable


class DocumentParser:
    name = "docling_optional_v2"
    default_max_file_bytes = 20 * 1024 * 1024
    supported_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("docling") is not None

    def supports(self, content_type: str) -> bool:
        return (content_type or "").lower().split(";", 1)[0] in self.supported_types

    def _require(self) -> None:
        if not self.available:
            raise ParserUnavailable("docling_parser_unavailable")

    def _path(self, snapshot: dict[str, Any]) -> Path:
        path = Path(str(snapshot.get("attachment_path") or ""))
        if not path.is_file():
            raise ParserUnavailable("document_attachment_unavailable")
        limit = int(snapshot.get("max_file_bytes") or self.default_max_file_bytes)
        if path.stat().st_size > limit:
            raise ParserUnavailable("document_too_large")
        return path

    @staticmethod
    def _page_number(item: Any) -> int | None:
        provenance = getattr(item, "prov", None) or []
        if not provenance:
            return None
        value = getattr(provenance[0], "page_no", None)
        return int(value) if value is not None else None

    def _convert(self, snapshot: dict[str, Any]) -> tuple[Path, Any]:
        self._require()
        path = self._path(snapshot)
        from docling.document_converter import DocumentConverter

        return path, DocumentConverter().convert(str(path)).document

    def extract_metadata(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        path = self._path(snapshot)
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "attachment_path": str(path),
            "filename": path.name,
            "mime_type": snapshot.get("content_type") or snapshot.get("mime_type"),
            "source_url": snapshot.get("source_url") or snapshot.get("original_url"),
            "file_hash": digest.hexdigest(),
            "file_size_bytes": path.stat().st_size,
        }

    def extract_text(self, snapshot: dict[str, Any]) -> str:
        _, document = self._convert(snapshot)
        return str(document.export_to_markdown() or "").strip()

    def extract_sections(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        _, document = self._convert(snapshot)
        return self._sections(document)

    def extract_tables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        _, document = self._convert(snapshot)
        return self._tables(document)

    def _sections(self, document: Any) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for item in list(getattr(document, "texts", None) or []):
            value = str(getattr(item, "text", "") or "").strip()
            if not value:
                continue
            label = str(getattr(item, "label", "") or "").lower()
            if "title" in label or "section" in label or "heading" in label:
                current = {
                    "section": value,
                    "page_number": self._page_number(item),
                    "text": "",
                }
                sections.append(current)
            elif current is not None:
                current["text"] = (current["text"] + "\n" + value).strip()
        return sections

    def _tables(self, document: Any) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        for index, table in enumerate(list(getattr(document, "tables", None) or []), start=1):
            markdown = ""
            rows: list[dict[str, Any]] = []
            try:
                frame = table.export_to_dataframe()
                rows = frame.fillna("").to_dict(orient="records")
                markdown = frame.to_markdown(index=False)
            except Exception:
                exporter = getattr(table, "export_to_markdown", None)
                if callable(exporter):
                    markdown = str(exporter() or "")
            tables.append(
                {
                    "table_number": str(index),
                    "page_number": self._page_number(table),
                    "columns": list(rows[0].keys()) if rows else [],
                    "rows": rows,
                    "markdown": markdown,
                }
            )
        return tables

    def build_citations(self, text: str) -> list[Citation]:
        if not text:
            return []
        return [
            Citation(
                excerpt=text[:500],
                char_start=0,
                char_end=min(len(text), 500),
                locator={"adapter": self.name},
            )
        ]

    def parse(self, snapshot: dict[str, Any]) -> ParseResult:
        path, document = self._convert(snapshot)
        text = str(document.export_to_markdown() or "").strip()
        metadata = self.extract_metadata({**snapshot, "attachment_path": str(path)})
        pages = getattr(document, "pages", None) or {}
        metadata["page_count"] = len(pages)
        sections = self._sections(document)
        tables = self._tables(document)
        citations: list[Citation] = []
        cursor = 0
        for item in list(getattr(document, "texts", None) or []):
            excerpt = str(getattr(item, "text", "") or "").strip()
            if not excerpt:
                continue
            start = text.find(excerpt[:120], cursor)
            start = start if start >= 0 else None
            end = start + len(excerpt) if start is not None else None
            citations.append(
                Citation(
                    excerpt=excerpt[:500],
                    char_start=start,
                    char_end=end,
                    page_number=self._page_number(item),
                    locator={
                        "adapter": self.name,
                        "page_number": self._page_number(item),
                    },
                )
            )
            if end is not None:
                cursor = end
        for table in tables:
            citations.append(
                Citation(
                    excerpt=str(table.get("markdown") or "")[:500],
                    page_number=table.get("page_number"),
                    table_number=table.get("table_number"),
                    locator={
                        "adapter": self.name,
                        "page_number": table.get("page_number"),
                        "table_number": table.get("table_number"),
                    },
                )
            )
        if not text:
            return ParseResult(
                text="",
                metadata=metadata,
                sections=sections,
                tables=tables,
                citations=[],
                parser_name=self.name,
                status="ocr_required",
            )
        return ParseResult(
            text=text,
            metadata=metadata,
            sections=sections,
            tables=tables,
            citations=citations or self.build_citations(text),
            parser_name=self.name,
        )
