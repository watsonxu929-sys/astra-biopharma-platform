from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c1_ingestion import ingest_payload
from app.v04db_prestructure import extract_source


def main() -> int:
    text = (
        "澄明生物于2026年6月完成A轮融资，融资金额约1.2亿元，由远景资本领投。"
        "公司创始人李明表示，项目CM-101计划于2027年进入II期临床。"
    )
    result = ingest_payload(
        {
            "batch": {"source_name": "v04db-demo", "source_type": "demo"},
            "records": [{
                "external_key": "v04db-demo-001",
                "title": "澄明生物完成A轮融资",
                "source_url": "https://example.test/v04db-demo",
                "content": text,
                "excerpt": text,
            }],
        },
        created_by="v04db-demo",
    )
    source = result["results"][0]["record"]
    extracted = extract_source(int(source["id"]), actor="v04db-demo")
    run = extracted["run"]
    print(f"[OK] Demo extraction run: {run['run_no']}")
    print(f"Candidates: {run['candidate_count']}")
    print(f"Open: http://127.0.0.1:8000/review/prestructure/runs/{run['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
