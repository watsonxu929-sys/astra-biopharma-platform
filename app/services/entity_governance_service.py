from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.settings import resolved_db_path
from app.v04c_review import db_connection


ENTITY_CONFIG = {
    "person": ("people", "external_id", "name"),
    "organization": ("organizations", "external_id", "COALESCE(NULLIF(name,''),standard_name)"),
    "project": ("projects", "external_id", "name"),
    "product": ("p3_product_assets", "external_id", "canonical_name"),
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_name(value: str) -> str:
    return re.sub(r"[\s\-_.·•（）()【】\[\]，,]+", "", (value or "").strip().casefold())


def normalize_identifier(kind: str, value: str) -> str:
    value = (value or "").strip().casefold()
    if kind == "official_domain":
        value = re.sub(r"^https?://", "", value).split("/", 1)[0].removeprefix("www.")
    return re.sub(r"\s+", "", value)


def _permissions(permissions: set[str] | None, required: str) -> None:
    if required not in (permissions or set()) and "manage_users" not in (permissions or set()):
        raise PermissionError(f"{required}_required")


def _entity_row(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> dict[str, Any] | None:
    if entity_type not in ENTITY_CONFIG:
        raise ValueError("unsupported_entity_type")
    table, key, label = ENTITY_CONFIG[entity_type]
    row = conn.execute(
        f"SELECT *, {label} AS canonical_label FROM {table} WHERE {key}=?", (entity_id,)
    ).fetchone()
    return dict(row) if row else None


def _active_redirect(conn: sqlite3.Connection, entity_type: str, entity_id: str) -> str | None:
    seen: set[str] = set()
    current = entity_id
    while current not in seen:
        seen.add(current)
        row = conn.execute(
            "SELECT target_entity_id FROM p3_entity_redirects WHERE entity_type=? AND source_entity_id=? AND status='active'",
            (entity_type, current),
        ).fetchone()
        if not row:
            return current if current != entity_id else None
        current = str(row[0])
    raise ValueError("redirect_cycle_detected")


class EntityRegistryService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def resolve_redirect(self, entity_type: str, entity_id: str) -> str:
        with db_connection(self.db_path) as conn:
            return _active_redirect(conn, entity_type, entity_id) or entity_id

    def get(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        with db_connection(self.db_path) as conn:
            resolved = _active_redirect(conn, entity_type, entity_id) or entity_id
            row = _entity_row(conn, entity_type, resolved)
            if not row:
                return None
            row["requested_id"] = entity_id
            row["resolved_id"] = resolved
            row["redirected"] = resolved != entity_id
            row["aliases"] = [dict(item) for item in conn.execute(
                "SELECT * FROM p3_entity_aliases WHERE entity_type=? AND entity_id=? AND review_status='approved' ORDER BY alias",
                (entity_type, resolved),
            )]
            row["external_identifiers"] = [dict(item) for item in conn.execute(
                "SELECT * FROM p3_entity_external_identifiers WHERE entity_type=? AND entity_id=? AND review_status='approved' ORDER BY identifier_type",
                (entity_type, resolved),
            )]
            return row

    def create_product(
        self, canonical_name: str, *, asset_type: str, actor: str, permissions: set[str],
        owner_organization_id: str | None = None, development_code: str = "", brand_name: str = "",
        target_text: str = "", modality: str = "", source: str = "manual",
        is_pilot: bool = False, pilot_batch_id: str | None = None,
    ) -> dict[str, Any]:
        _permissions(permissions, "edit_data")
        ts = now_iso()
        external_id = f"PA-{uuid.uuid4().hex[:12].upper()}"
        with db_connection(self.db_path) as conn:
            if owner_organization_id and not _entity_row(conn, "organization", owner_organization_id):
                raise ValueError("owner_organization_not_found")
            cur = conn.execute(
                """INSERT INTO p3_product_assets(external_id,canonical_name,asset_type,development_code,brand_name,target_text,modality,owner_organization_id,status,completeness,review_status,visibility,source,is_pilot,pilot_batch_id,created_by,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,'active',50,'pending_review','internal',?,?,?,?,?,?)""",
                (external_id, canonical_name.strip(), asset_type, development_code, brand_name, target_text,
                 modality, owner_organization_id, source, int(is_pilot), pilot_batch_id, actor, ts, ts),
            )
            return dict(conn.execute("SELECT * FROM p3_product_assets WHERE id=?", (cur.lastrowid,)).fetchone())
    def add_alias(
        self, entity_type: str, entity_id: str, alias: str, *, alias_type: str,
        actor: str, permissions: set[str], source: str = "manual", evidence_snapshot_id: int | None = None,
        is_pilot: bool = False, pilot_batch_id: str | None = None,
    ) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            entity_id = _active_redirect(conn, entity_type, entity_id) or entity_id
            if not _entity_row(conn, entity_type, entity_id):
                raise ValueError("entity_not_found")
            cur = conn.execute(
                """INSERT INTO p3_entity_aliases(entity_type,entity_id,alias,alias_type,normalized_alias,source,evidence_snapshot_id,review_status,is_pilot,pilot_batch_id,created_by,reviewed_by,reviewed_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,'approved',?,?,?,?,?,?,?)""",
                (entity_type, entity_id, alias.strip(), alias_type, normalize_name(alias), source,
                 evidence_snapshot_id, int(is_pilot), pilot_batch_id, actor, actor, ts, ts, ts),
            )
            return dict(conn.execute("SELECT * FROM p3_entity_aliases WHERE id=?", (cur.lastrowid,)).fetchone())

    def add_external_identifier(
        self, entity_type: str, entity_id: str, identifier_type: str, identifier_value: str, *,
        actor: str, permissions: set[str], authority: str = "", market: str = "",
        source: str = "manual", evidence_snapshot_id: int | None = None,
    ) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        ts = now_iso()
        normalized = normalize_identifier(identifier_type, identifier_value)
        with db_connection(self.db_path) as conn:
            entity_id = _active_redirect(conn, entity_type, entity_id) or entity_id
            if not _entity_row(conn, entity_type, entity_id):
                raise ValueError("entity_not_found")
            cur = conn.execute(
                """INSERT INTO p3_entity_external_identifiers(entity_type,entity_id,identifier_type,identifier_value,normalized_value,market,authority,source,evidence_snapshot_id,review_status,is_sensitive,created_by,reviewed_by,reviewed_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,'approved',0,?,?,?,?,?)""",
                (entity_type, entity_id, identifier_type, identifier_value.strip(), normalized, market,
                 authority, source, evidence_snapshot_id, actor, actor, ts, ts, ts),
            )
            return dict(conn.execute("SELECT * FROM p3_entity_external_identifiers WHERE id=?", (cur.lastrowid,)).fetchone())


class EntityResolutionService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def propose(
        self, entity_type: str, raw_name: str, *, external_identifiers: dict[str, str] | None = None,
        context: dict[str, str] | None = None, source_record_type: str = "manual",
        source_record_id: str = "", actor: str = "system", is_pilot: bool = False,
        pilot_batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if entity_type not in ENTITY_CONFIG:
            raise ValueError("unsupported_entity_type")
        normalized = normalize_name(raw_name)
        external_identifiers = external_identifiers or {}
        context = context or {}
        matches: dict[str, dict[str, Any]] = {}
        with db_connection(self.db_path) as conn:
            for kind, value in external_identifiers.items():
                norm = normalize_identifier(kind, value)
                for row in conn.execute(
                    """SELECT entity_id FROM p3_entity_external_identifiers
                       WHERE entity_type=? AND identifier_type=? AND normalized_value=? AND review_status='approved'""",
                    (entity_type, kind, norm),
                ):
                    matches[str(row[0])] = {"score": .99, "strength": "strong", "features": {kind: "exact"}}
            table, key, label = ENTITY_CONFIG[entity_type]
            for row in conn.execute(f"SELECT {key} AS entity_id,{label} AS label FROM {table}"):
                if normalize_name(str(row["label"] or "")) == normalized:
                    score = .86
                    strength = "medium"
                    if entity_type == "person" and not (context.get("organization_id") or context.get("role")):
                        score, strength = .48, "weak"
                    prior = matches.get(str(row["entity_id"]))
                    if not prior or score > prior["score"]:
                        matches[str(row["entity_id"])] = {"score": score, "strength": strength, "features": {"canonical_name": "exact"}, "label": row["label"]}
            for row in conn.execute(
                """SELECT entity_id,alias FROM p3_entity_aliases
                   WHERE entity_type=? AND normalized_alias=? AND review_status='approved'""",
                (entity_type, normalized),
            ):
                matches.setdefault(str(row["entity_id"]), {"score": .78, "strength": "medium", "features": {"approved_alias": row["alias"]}})
            created: list[dict[str, Any]] = []
            for entity_id, match in sorted(matches.items(), key=lambda item: item[1]["score"], reverse=True):
                entity = _entity_row(conn, entity_type, entity_id)
                candidate_no = f"ER-{uuid.uuid4().hex[:12].upper()}"
                status = "ambiguous" if match["strength"] == "weak" else "pending"
                cur = conn.execute(
                    """INSERT INTO p3_entity_resolution_candidates(candidate_no,candidate_type,raw_name,normalized_name,possible_entity_id,possible_entity_label,matching_features_json,score,match_strength,generated_by,source_record_type,source_record_id,resolution_status,is_pilot,pilot_batch_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (candidate_no, entity_type, raw_name.strip(), normalized, entity_id,
                     (entity or {}).get("canonical_label", match.get("label", "")), json.dumps(match["features"], ensure_ascii=False),
                     match["score"], match["strength"], actor, source_record_type, source_record_id,
                     status, int(is_pilot), pilot_batch_id, now_iso(), now_iso()),
                )
                created.append(dict(conn.execute("SELECT * FROM p3_entity_resolution_candidates WHERE id=?", (cur.lastrowid,)).fetchone()))
            if not created:
                candidate_no = f"ER-{uuid.uuid4().hex[:12].upper()}"
                cur = conn.execute(
                    """INSERT INTO p3_entity_resolution_candidates(candidate_no,candidate_type,raw_name,normalized_name,matching_features_json,score,match_strength,generated_by,source_record_type,source_record_id,resolution_status,is_pilot,pilot_batch_id,created_at,updated_at)
                       VALUES (?,?,?,?, '{}',0,'weak',?,?,?,'needs_more_evidence',?,?,?,?)""",
                    (candidate_no, entity_type, raw_name.strip(), normalized, actor, source_record_type,
                     source_record_id, int(is_pilot), pilot_batch_id, now_iso(), now_iso()),
                )
                created.append(dict(conn.execute("SELECT * FROM p3_entity_resolution_candidates WHERE id=?", (cur.lastrowid,)).fetchone()))
            return created

    def review(self, candidate_id: int, decision: str, *, actor: str, permissions: set[str], note: str = "") -> dict[str, Any]:
        _permissions(permissions, "review_data")
        if decision not in {"matched", "create_new", "rejected", "ambiguous", "needs_more_evidence"}:
            raise ValueError("invalid_resolution_decision")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM p3_entity_resolution_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("resolution_candidate_not_found")
            if decision == "matched" and not row["possible_entity_id"]:
                raise ValueError("matched_entity_required")
            conn.execute(
                "UPDATE p3_entity_resolution_candidates SET resolution_status=?,review_note=?,reviewer=?,reviewed_at=?,updated_at=? WHERE id=?",
                (decision, note, actor, now_iso(), now_iso(), candidate_id),
            )
            return dict(conn.execute("SELECT * FROM p3_entity_resolution_candidates WHERE id=?", (candidate_id,)).fetchone())


class EntityMergeService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def preview(
        self, entity_type: str, source_entity_id: str, target_entity_id: str, *, reason: str,
        actor: str, evidence: list[dict[str, Any]] | None = None,
        is_pilot: bool = False, pilot_batch_id: str | None = None,
    ) -> dict[str, Any]:
        if source_entity_id == target_entity_id:
            raise ValueError("merge_source_equals_target")
        with db_connection(self.db_path) as conn:
            source = _entity_row(conn, entity_type, source_entity_id)
            target = _entity_row(conn, entity_type, target_entity_id)
            if not source or not target:
                raise ValueError("merge_entity_not_found")
            alias_ids = [int(row[0]) for row in conn.execute("SELECT id FROM p3_entity_aliases WHERE entity_type=? AND entity_id=?", (entity_type, source_entity_id))]
            identifier_rows = [dict(row) for row in conn.execute("SELECT * FROM p3_entity_external_identifiers WHERE entity_type=? AND entity_id=?", (entity_type, source_entity_id))]
            conflicts = []
            for identifier in identifier_rows:
                duplicate = conn.execute(
                    "SELECT id FROM p3_entity_external_identifiers WHERE entity_type=? AND entity_id=? AND identifier_type=? AND normalized_value=? AND review_status<>'rejected'",
                    (entity_type, target_entity_id, identifier["identifier_type"], identifier["normalized_value"]),
                ).fetchone()
                if duplicate:
                    conflicts.append({"source_identifier_id": identifier["id"], "target_identifier_id": duplicate[0]})
            relation_ids = [int(row[0]) for row in conn.execute(
                "SELECT id FROM p3_canonical_relationships WHERE (subject_type=? AND subject_id=?) OR (object_type=? AND object_id=?)",
                (entity_type, source_entity_id, entity_type, source_entity_id),
            )]
            preview = {"source": source, "target": target, "alias_ids": alias_ids,
                       "identifier_ids": [int(row["id"]) for row in identifier_rows],
                       "relationship_ids": relation_ids, "identifier_conflicts": conflicts,
                       "canonical_fields_preserved": True}
            ts = now_iso()
            cur = conn.execute(
                """INSERT INTO p3_entity_merge_records(merge_no,source_entity_id,target_entity_id,entity_type,merge_reason,merge_evidence_json,preview_json,initiated_by,merge_status,is_pilot,pilot_batch_id,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?, 'preview',?,?,?,?)""",
                (f"MRG-{uuid.uuid4().hex[:12].upper()}", source_entity_id, target_entity_id, entity_type,
                 reason, json.dumps(evidence or [], ensure_ascii=False), json.dumps(preview, ensure_ascii=False, default=str),
                 actor, int(is_pilot), pilot_batch_id, ts, ts),
            )
            result = dict(conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (cur.lastrowid,)).fetchone())
            result["preview"] = preview
            return result

    def submit(self, merge_id: int, *, actor: str, permissions: set[str]) -> dict[str, Any]:
        _permissions(permissions, "edit_data")
        with db_connection(self.db_path) as conn:
            changed = conn.execute(
                "UPDATE p3_entity_merge_records SET merge_status='pending_approval',updated_at=? WHERE id=? AND merge_status='preview'",
                (now_iso(), merge_id),
            ).rowcount
            if not changed:
                raise ValueError("merge_preview_not_submittable")
            return dict(conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (merge_id,)).fetchone())

    def execute(self, merge_id: int, *, actor: str, permissions: set[str]) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (merge_id,)).fetchone()
            if not row or row["merge_status"] != "pending_approval":
                raise ValueError("merge_not_pending_approval")
            preview = json.loads(row["preview_json"])
            if preview.get("identifier_conflicts"):
                raise ValueError("merge_identifier_conflict")
            entity_type, source, target = row["entity_type"], row["source_entity_id"], row["target_entity_id"]
            if _active_redirect(conn, entity_type, target):
                target = _active_redirect(conn, entity_type, target) or target
            table, key, _ = ENTITY_CONFIG[entity_type]
            current = _entity_row(conn, entity_type, source)
            rollback = {"source_state": {k: current.get(k) for k in ("is_active", "status", "deactivated_at", "deactivated_reason") if k in current},
                        "alias_ids": preview["alias_ids"], "identifier_ids": preview["identifier_ids"],
                        "relationship_ids": preview["relationship_ids"]}
            conn.execute("UPDATE p3_entity_aliases SET entity_id=?,updated_at=? WHERE entity_type=? AND entity_id=?", (target, now_iso(), entity_type, source))
            conn.execute("UPDATE p3_entity_external_identifiers SET entity_id=?,updated_at=? WHERE entity_type=? AND entity_id=?", (target, now_iso(), entity_type, source))
            conn.execute("UPDATE p3_canonical_relationships SET subject_id=?,updated_at=? WHERE subject_type=? AND subject_id=?", (target, now_iso(), entity_type, source))
            conn.execute("UPDATE p3_canonical_relationships SET object_id=?,updated_at=? WHERE object_type=? AND object_id=?", (target, now_iso(), entity_type, source))
            ts = now_iso()
            conn.execute(
                "INSERT INTO p3_entity_redirects(entity_type,source_entity_id,target_entity_id,merge_record_id,status,created_at) VALUES (?,?,?,?,'active',?)",
                (entity_type, source, target, merge_id, ts),
            )
            if entity_type == "product":
                conn.execute(f"UPDATE {table} SET status='merged',updated_at=? WHERE {key}=?", (ts, source))
            else:
                conn.execute(f"UPDATE {table} SET is_active=0,deactivated_at=?,deactivated_reason='p3_entity_merge' WHERE {key}=?", (ts, source))
            conn.execute(
                """UPDATE p3_entity_merge_records SET target_entity_id=?,approved_by=?,merged_at=?,affected_relations_json=?,affected_aliases_json=?,rollback_payload_json=?,merge_status='merged',updated_at=? WHERE id=?""",
                (target, actor, ts, json.dumps(preview["relationship_ids"]), json.dumps(preview["alias_ids"]),
                 json.dumps(rollback, ensure_ascii=False), ts, merge_id),
            )
            conn.execute("INSERT INTO p3_relationship_audit(action,merge_record_id,actor,after_json,reason,created_at) VALUES ('entity_merge',?,?,?,?,?)",
                         (merge_id, actor, json.dumps({"source": source, "target": target}), row["merge_reason"], ts))
            return dict(conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (merge_id,)).fetchone())

    def rollback(self, merge_id: int, *, actor: str, permissions: set[str], reason: str) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (merge_id,)).fetchone()
            if not row or row["merge_status"] != "merged":
                raise ValueError("merge_not_rollbackable")
            payload = json.loads(row["rollback_payload_json"])
            entity_type, source = row["entity_type"], row["source_entity_id"]
            table, key, _ = ENTITY_CONFIG[entity_type]
            for alias_id in payload.get("alias_ids", []):
                conn.execute("UPDATE p3_entity_aliases SET entity_id=?,updated_at=? WHERE id=?", (source, now_iso(), alias_id))
            for identifier_id in payload.get("identifier_ids", []):
                conn.execute("UPDATE p3_entity_external_identifiers SET entity_id=?,updated_at=? WHERE id=?", (source, now_iso(), identifier_id))
            for relationship_id in payload.get("relationship_ids", []):
                conn.execute("UPDATE p3_canonical_relationships SET subject_id=CASE WHEN subject_type=? AND subject_id=? THEN ? ELSE subject_id END, object_id=CASE WHEN object_type=? AND object_id=? THEN ? ELSE object_id END,updated_at=? WHERE id=?",
                             (entity_type, row["target_entity_id"], source, entity_type, row["target_entity_id"], source, now_iso(), relationship_id))
            state = payload.get("source_state", {})
            if entity_type == "product":
                conn.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE {key}=?", (state.get("status", "active"), now_iso(), source))
            else:
                conn.execute(f"UPDATE {table} SET is_active=?,deactivated_at=?,deactivated_reason=? WHERE {key}=?",
                             (state.get("is_active", 1), state.get("deactivated_at"), state.get("deactivated_reason"), source))
            ts = now_iso()
            conn.execute("UPDATE p3_entity_redirects SET status='rolled_back',rolled_back_at=? WHERE merge_record_id=?", (ts, merge_id))
            conn.execute("UPDATE p3_entity_merge_records SET merge_status='rolled_back',rollback_by=?,rollback_reason=?,rolled_back_at=?,updated_at=? WHERE id=?",
                         (actor, reason, ts, ts, merge_id))
            conn.execute("INSERT INTO p3_relationship_audit(action,merge_record_id,actor,reason,created_at) VALUES ('entity_merge_rollback',?,?,?,?)",
                         (merge_id, actor, reason, ts))
            return dict(conn.execute("SELECT * FROM p3_entity_merge_records WHERE id=?", (merge_id,)).fetchone())


def list_resolution_candidates(db_path: str | Path | None = None, status: str = "") -> list[dict[str, Any]]:
    with db_connection(db_path or resolved_db_path()) as conn:
        sql = "SELECT * FROM p3_entity_resolution_candidates"
        params: tuple[Any, ...] = ()
        if status:
            sql += " WHERE resolution_status=?"; params = (status,)
        return [dict(row) for row in conn.execute(sql + " ORDER BY score DESC,id DESC", params)]


def list_merge_records(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(db_path or resolved_db_path()) as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM p3_entity_merge_records ORDER BY id DESC")]
