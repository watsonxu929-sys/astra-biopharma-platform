from __future__ import annotations

import hashlib
import re


def text_hash(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evidence_excerpt(text: str, limit: int = 280) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:limit]


def split_blocks(text: str, page_type: str) -> list[dict[str, object]]:
    raw = (text or "").strip()
    if not raw:
        return []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    blocks: list[str] = []
    if page_type in {"team_page", "product_pipeline", "multi_subject_list"}:
        current: list[str] = []
        for line in lines:
            boundary = _looks_like_card_start(line, page_type)
            if boundary and current:
                current_text = "\n".join(current).strip()
                if not _is_heading_only(current_text):
                    blocks.append(current_text)
                current = [line]
            else:
                current.append(line)
                if len(" ".join(current)) > 900:
                    current_text = "\n".join(current).strip()
                    if not _is_heading_only(current_text):
                        blocks.append(current_text)
                    current = []
        if current:
            current_text = "\n".join(current).strip()
            if not _is_heading_only(current_text):
                blocks.append(current_text)
    else:
        parts = re.split(r"\n{2,}|(?<=[。.!?])\s+(?=[^\s])", raw)
        blocks = [part.strip() for part in parts if len(part.strip()) >= 12]
    if not blocks and lines:
        blocks = lines
    result: list[dict[str, object]] = []
    offset = 0
    for index, block in enumerate(blocks[:80]):
        start = raw.find(block, offset)
        if start < 0:
            start = offset
        end = start + len(block)
        offset = end
        block_type = "card" if page_type in {"team_page", "product_pipeline", "multi_subject_list"} else "paragraph"
        if page_type == "news_event":
            block_type = "article_section"
        result.append(
            {
                "index": index,
                "block_type": block_type,
                "text": block,
                "hash": text_hash(block),
                "char_start": start,
                "char_end": end,
                "evidence_excerpt": evidence_excerpt(block),
                "confidence_score": 76 if len(block) >= 30 else 52,
                "warnings": _block_warnings(block, page_type),
            }
        )
    return result


def _looks_like_card_start(line: str, page_type: str) -> bool:
    stripped = line.strip()
    if len(stripped) > 90:
        return False
    if page_type == "team_page":
        if stripped in {"团队", "管理团队", "领导团队", "核心团队", "董事会"}:
            return False
        return bool(re.search(r"^[\u4e00-\u9fa5]{2,4}\s*[｜|\-—,，]\s*.{2,40}$", stripped)) or bool(
            re.search(r"^(Dr\.|Prof\.|Mr\.|Ms\.)\s+[A-Z][A-Za-z .-]{2,50}", stripped)
        )
    if page_type == "product_pipeline":
        return bool(re.search(r"^(?:[A-Z]{2,}[A-Z0-9-]*|[\u4e00-\u9fa5A-Za-z0-9-]{3,40})\s*[：:｜|\-—]?", stripped))
    return bool(re.match(r"^\d+[.)、]\s+", stripped)) or bool(re.search(r"[：:]\s*$", stripped))


def _block_warnings(block: str, page_type: str) -> list[str]:
    warnings: list[str] = []
    if len(block.strip()) < 20:
        warnings.append("short_block")
    if page_type == "team_page" and block.strip() in {"团队", "管理团队", "核心团队"}:
        warnings.append("heading_only")
    if len(block) > 3000:
        warnings.append("long_mixed_block")
    return warnings


def _is_heading_only(value: str) -> bool:
    return value.strip() in {"团队", "管理团队", "领导团队", "核心团队", "董事会", "产品管线", "政策公告"}
