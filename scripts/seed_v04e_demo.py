from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c_review import db_connection  # noqa: E402
from app.v04e_entity_resolution import add_alias, ensure_v04e_schema, scan_duplicates  # noqa: E402


def main() -> int:
    ensure_v04e_schema()
    now = datetime.now().isoformat(timespec="seconds")
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT external_id FROM organizations WHERE external_id IN ('ORG-V04E-DEMO-1','ORG-V04E-DEMO-2')"
        ).fetchall()
        ids = {row["external_id"] for row in existing}
        if "ORG-V04E-DEMO-1" not in ids:
            conn.execute(
                """
                INSERT INTO organizations(
                    external_id,standard_name,org_type,region,visibility,verification_status,is_active,created_at
                ) VALUES ('ORG-V04E-DEMO-1','星源生物科技有限公司','生物科技','上海','内部','待核验',1,?)
                """,
                (now,),
            )
        if "ORG-V04E-DEMO-2" not in ids:
            conn.execute(
                """
                INSERT INTO organizations(
                    external_id,standard_name,org_type,region,visibility,verification_status,is_active,created_at
                ) VALUES ('ORG-V04E-DEMO-2','星源生物','生物科技','上海','内部','待核验',1,?)
                """,
                (now,),
            )
    try:
        add_alias("organization", "ORG-V04E-DEMO-1", "StarOrigin Bio", alias_type="english_name", source_note="v0.4E-A演示", actor="demo")
    except ValueError:
        pass
    result = scan_duplicates("organization", threshold=0.70, actor="demo")
    print(f"[OK] Demo data ready. New candidates: {result['created']}, updated: {result['updated']}")
    print("Open: http://127.0.0.1:8000/review/entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
