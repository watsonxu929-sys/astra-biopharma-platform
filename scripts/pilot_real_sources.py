from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_service import create_collection_source
from app.services.pipeline import create_pipeline_run, continue_pipeline
from app.services.pipeline.pipeline_common import db_connection, now
from scripts.migrate_v05i import migrate

CONFIG_PATH = ROOT / "config" / "pilot_sources.yaml"


def _load_sources() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not CONFIG_PATH.exists():
        return rows
    current: dict[str, str] | None = None
    for raw in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("- key:"):
            if current:
                rows.append(current)
            current = {"key": line.split(":", 1)[1].strip()}
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip().strip('"')
    if current:
        rows.append(current)
    return rows


def _record_result(source: dict[str, str], result: str, passed: bool, run_id: int | None = None) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO v05i_pilot_source_results(source_key,source_name,source_type,expected_structure,last_run_at,last_result,passed,known_limits,acceptance_note,pipeline_run_id,created_at,updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source.get("key"), source.get("name"), source.get("source_type"), source.get("expected_structure"), now(), result[:800], int(passed), source.get("note"), "manual acceptance required", run_id, now(), now()),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or confirmed pilot for configured real sources")
    parser.add_argument("--list", action="store_true", help="List configured pilot sources without running collection")
    parser.add_argument("--source-id", type=int, help="1-based source index from config")
    parser.add_argument("--group", default="", help="Only include sources whose group matches this value")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; this is also the default without --confirm")
    parser.add_argument("--confirm", action="store_true", help="Required before real network access")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    migrate(backup=False)
    sources = _load_sources()
    if args.group:
        sources = [source for source in sources if source.get("group", "") == args.group]
    if args.list:
        if not sources:
            print("未配置真实来源试运行清单。")
            return 0
        for idx, source in enumerate(sources, start=1):
            print(f"{idx}. {source.get('key')} | {source.get('name')} | {source.get('source_type')} | group={source.get('group','default')} | allow_real_run={source.get('allow_real_run','false')}")
        return 0
    if args.source_id:
        if args.source_id < 1 or args.source_id > len(sources):
            print("source-id 超出当前清单范围。")
            return 2
        selected = [sources[args.source_id - 1]]
    else:
        selected = sources
    if not selected:
        print("没有匹配的试运行来源。")
        return 0
    for source in selected:
        if not args.confirm:
            print(f"DRY-RUN {source.get('key')}: {source.get('url')} max_links={min(int(source.get('max_links') or 10), args.limit)} robots=not_checked_dry_run")
            _record_result(source, "dry_run_only", False)
            continue
        if source.get("allow_real_run", "false").lower() != "true":
            print(f"SKIP {source.get('key')}: allow_real_run is false")
            _record_result(source, "allow_real_run_false", False)
            continue
        row = create_collection_source(
            name=source.get("name", "pilot source"),
            source_type=source.get("source_type", "webpage"),
            url=source.get("url", ""),
            collection_mode=source.get("collection_mode", "http"),
            allowed_domains=source.get("allowed_domains", ""),
            compliance_note=source.get("note", ""),
            max_links=min(int(source.get("max_links") or 10), args.limit, 20),
            crawl_detail_pages=source.get("source_type") == "list_page",
        )
        run = create_pipeline_run(row["id"], created_by="pilot_real_sources", pilot=True, dry_run=True)
        result = continue_pipeline(run["id"], actor="pilot_real_sources")
        _record_result(source, str(result), result.get("status") in {"waiting_review", "partial", "completed"}, run["id"])
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
