from __future__ import annotations

import re

from bs4 import BeautifulSoup
from trafilatura import extract


def extract_main_text(raw_html: str) -> tuple[str, str]:
    """Return normalized main text and the extractor used."""
    text = extract(
        raw_html or "",
        output_format="txt",
        include_comments=False,
        deduplicate=True,
    ) or ""
    method = "trafilatura"
    if not text.strip():
        soup = BeautifulSoup(raw_html or "", "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        text = (soup.body or soup).get_text("\n", strip=True)
        method = "beautifulsoup_text_fallback"
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if len(line) >= 2), method
