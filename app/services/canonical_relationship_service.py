from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.settings import resolved_db_path
from app.v04c_review import db_connection
from app.services.entity_governance_service import ENTITY_CONFIG, _active_redirect, _entity_row, _permissions, now_iso


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _overlap(a_from: str | None, a_to: str | None, b_from: str | None, b_to: str | None) -> bool:
    start_a, end_a = _parse_date(a_from) or date.min, _parse_date(a_to) or date.max
    start_b, end_b = _parse_date(b_from) or date.min, _parse_date(b_to) or date.max
    return start_a <= end_b and start_b <= end_a


def _type_row(conn: sqlite3.Connection, relationship_type: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM p3_relationship_type_registry WHERE relationship_type=? AND active=1", (relationship_type,)).fetchone()
    if not row:
        raise ValueError("relationship_type_not_registered")
    return row


def _validate_endpoints(conn: sqlite3.Connection, subject_type: str, subject_id: str, type_row: sqlite3.Row, object_type: str, object_id: str) -> tuple[str, str]:
    if subject_type not in json.loads(type_row["subject_types_json"]) or object_type not in json.loads(type_row["object_types_json"]):
        raise ValueError("relationship_endpoint_type_mismatch")
    subject_id = _active_redirect(conn, subject_type, subject_id) or subject_id
    object_id = _active_redirect(conn, object_type, object_id) or object_id
    if not _entity_row(conn, subject_type, subject_id) or not _entity_row(conn, object_type, object_id):
        raise ValueError("relationship_endpoint_not_found")
    if subject_type == object_type and subject_id == object_id:
        raise ValueError("self_relationship_not_allowed")
    return subject_id, object_id


def _evidence_hash(item: dict[str, Any]) -> str:
    payload = "|".join(str(item.get(key) or "") for key in ("evidence_snapshot_id", "raw_intelligence_id", "fact_candidate_id", "fact_assertion_id", "industry_event_id", "evidence_text", "page_number", "source_url"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit(conn: sqlite3.Connection, action: str, actor: str, *, relationship_id: int | None = None, candidate_id: int | None = None, before: Any = None, after: Any = None, reason: str = "") -> None:
    conn.execute(
        "INSERT INTO p3_relationship_audit(action,relationship_id,relationship_candidate_id,actor,before_json,after_json,reason,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (action, relationship_id, candidate_id, actor, json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
         json.dumps(after, ensure_ascii=False, default=str) if after is not None else None, reason, now_iso()),
    )


class CanonicalRelationshipService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def create_candidate(
        self, *, subject_type: str, subject_id: str, relationship_type: str,
        object_type: str, object_id: str, actor: str, valid_from: str | None = None,
        valid_to: str | None = None, confidence: int = 50, evidence: list[dict[str, Any]] | None = None,
        source_record_type: str = "manual", source_record_id: str = "",
        visibility: str = "internal",
        is_pilot: bool = False, pilot_batch_id: str | None = None,
    ) -> dict[str, Any]:
        if valid_from and valid_to and _parse_date(valid_from) > _parse_date(valid_to):
            raise ValueError("invalid_relationship_period")
        with db_connection(self.db_path) as conn:
            type_row = _type_row(conn, relationship_type)
            subject_id, object_id = _validate_endpoints(conn, subject_type, subject_id, type_row, object_type, object_id)
            similar, conflicts = [], []
            for row in conn.execute(
                """SELECT id,valid_from,valid_to,review_status FROM p3_canonical_relationships
                   WHERE subject_type=? AND subject_id=? AND relationship_type=? AND object_type=? AND object_id=? AND review_status<>'archived'""",
                (subject_type, subject_id, relationship_type, object_type, object_id),
            ):
                similar.append(int(row["id"]))
                if _overlap(valid_from, valid_to, row["valid_from"], row["valid_to"]):
                    conflicts.append(int(row["id"]))
            status = "conflict" if conflicts else "pending"
            ts = now_iso()
            cur = conn.execute(
                """INSERT INTO p3_relationship_candidates(candidate_no,subject_type,subject_id,relationship_type,object_type,object_id,valid_from,valid_to,confidence,source_record_type,source_record_id,evidence_json,similar_relationship_ids_json,conflict_relationship_ids_json,status,visibility,is_pilot,pilot_batch_id,created_by,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"RC-{uuid.uuid4().hex[:12].upper()}", subject_type, subject_id, relationship_type,
                 object_type, object_id, valid_from, valid_to, max(0, min(confidence, 100)),
                 source_record_type, source_record_id, json.dumps(evidence or [], ensure_ascii=False),
                 json.dumps(similar), json.dumps(conflicts), status, visibility, int(is_pilot), pilot_batch_id, actor, ts, ts),
            )
            result = dict(conn.execute("SELECT * FROM p3_relationship_candidates WHERE id=?", (cur.lastrowid,)).fetchone())
            _audit(conn, "relationship_candidate_created", actor, candidate_id=result["id"], after=result)
            return result

    def review_candidate(
        self, candidate_id: int, decision: str, *, actor: str, permissions: set[str], note: str = "",
        revision: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        if decision not in {"approved", "rejected", "needs_more_evidence"}:
            raise ValueError("invalid_relationship_decision")
        with db_connection(self.db_path) as conn:
            candidate = conn.execute("SELECT * FROM p3_relationship_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not candidate or candidate["status"] not in {"pending", "conflict", "needs_more_evidence"}:
                raise ValueError("relationship_candidate_not_reviewable")
            data = dict(candidate)
            if revision:
                for key in ("valid_from", "valid_to", "confidence", "relationship_type"):
                    if key in revision:
                        data[key] = revision[key]
            evidence = json.loads(data["evidence_json"])
            type_row = _type_row(conn, data["relationship_type"])
            if decision == "approved" and type_row["risk_level"] == "high" and not evidence:
                raise ValueError("high_risk_relationship_requires_evidence")
            relationship = None
            if decision == "approved":
                relationship = self._insert_relationship(conn, data, actor, evidence, note)
            ts = now_iso()
            conn.execute(
                "UPDATE p3_relationship_candidates SET status=?,revision_json=?,reviewed_by=?,reviewed_at=?,review_note=?,updated_at=? WHERE id=?",
                (decision, json.dumps(revision or {}, ensure_ascii=False), actor, ts, note, ts, candidate_id),
            )
            result = dict(conn.execute("SELECT * FROM p3_relationship_candidates WHERE id=?", (candidate_id,)).fetchone())
            result["relationship"] = relationship
            _audit(conn, f"relationship_candidate_{decision}", actor, candidate_id=candidate_id, before=dict(candidate), after=result, reason=note)
            return result

    def _insert_relationship(self, conn: sqlite3.Connection, data: dict[str, Any], actor: str, evidence: list[dict[str, Any]], note: str) -> dict[str, Any]:
        type_row = _type_row(conn, data["relationship_type"])
        subject_id, object_id = _validate_endpoints(conn, data["subject_type"], data["subject_id"], type_row, data["object_type"], data["object_id"])
        ts = now_iso()
        cur = conn.execute(
            """INSERT INTO p3_canonical_relationships(relationship_no,subject_type,subject_id,relationship_type,object_type,object_id,direction,valid_from,valid_to,is_current,confidence,review_status,evidence_status,source_count,visibility,legacy_relation_id,is_pilot,pilot_batch_id,created_by,reviewed_by,reviewed_at,review_note,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"REL-{uuid.uuid4().hex[:12].upper()}", data["subject_type"], subject_id, data["relationship_type"],
             data["object_type"], object_id, "symmetric" if type_row["is_symmetric"] else "directed",
             data.get("valid_from"), data.get("valid_to"), int(not bool(data.get("valid_to"))), int(data["confidence"]),
             "approved", "evidence_backed" if evidence else "manual_unverified", len({str(item.get("source_url") or item.get("evidence_snapshot_id") or item.get("raw_intelligence_id") or "manual") for item in evidence}),
             data.get("visibility", "internal"), data.get("legacy_relation_id"), int(data.get("is_pilot", 0)), data.get("pilot_batch_id"), actor, actor, ts, note, ts, ts),
        )
        relationship_id = int(cur.lastrowid)
        for item in evidence:
            conn.execute(
                """INSERT OR IGNORE INTO p3_relationship_evidence(relationship_id,evidence_snapshot_id,raw_intelligence_id,fact_candidate_id,fact_assertion_id,industry_event_id,evidence_text,page_number,locator_json,source_url,source_date,evidence_strength,evidence_hash,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (relationship_id, item.get("evidence_snapshot_id"), item.get("raw_intelligence_id"), item.get("fact_candidate_id"),
                 item.get("fact_assertion_id"), item.get("industry_event_id"), str(item.get("evidence_text") or "人工确认关系"),
                 item.get("page_number"), json.dumps(item.get("locator") or {}, ensure_ascii=False), item.get("source_url"), item.get("source_date"),
                 item.get("evidence_strength", "supporting"), _evidence_hash(item), ts),
            )
        result = dict(conn.execute("SELECT * FROM p3_canonical_relationships WHERE id=?", (relationship_id,)).fetchone())
        _audit(conn, "relationship_approved", actor, relationship_id=relationship_id, after=result, reason=note)
        return result

    def archive(self, relationship_id: int, *, actor: str, permissions: set[str], reason: str) -> dict[str, Any]:
        _permissions(permissions, "review_data")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM p3_canonical_relationships WHERE id=?", (relationship_id,)).fetchone()
            if not row:
                raise ValueError("relationship_not_found")
            conn.execute("UPDATE p3_canonical_relationships SET review_status='archived',is_current=0,review_note=?,updated_at=? WHERE id=?", (reason, now_iso(), relationship_id))
            result = dict(conn.execute("SELECT * FROM p3_canonical_relationships WHERE id=?", (relationship_id,)).fetchone())
            _audit(conn, "relationship_archived", actor, relationship_id=relationship_id, before=dict(row), after=result, reason=reason)
            return result

    def detail(self, relationship_id: int, *, include_private: bool = False) -> dict[str, Any] | None:
        with db_connection(self.db_path) as conn:
            clause = "" if include_private else " AND visibility IN ('public','internal')"
            row = conn.execute("SELECT * FROM p3_canonical_relationships WHERE id=?" + clause, (relationship_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["evidence"] = [dict(item) for item in conn.execute("SELECT * FROM p3_relationship_evidence WHERE relationship_id=? ORDER BY id", (relationship_id,))]
            return result

    def entity_relationships(self, entity_type: str, entity_id: str, *, history: bool = False, include_private: bool = False) -> list[dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            entity_id = _active_redirect(conn, entity_type, entity_id) or entity_id
            clauses = ["review_status='approved'", "((subject_type=? AND subject_id=?) OR (object_type=? AND object_id=?))"]
            params: list[Any] = [entity_type, entity_id, entity_type, entity_id]
            if not history:
                clauses.append("is_current=1")
            if not include_private:
                clauses.append("visibility IN ('public','internal')")
            return [dict(row) for row in conn.execute("SELECT * FROM p3_canonical_relationships WHERE " + " AND ".join(clauses) + " ORDER BY is_current DESC,valid_from DESC,id DESC", params)]


class RelationshipNetworkService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def find_paths(
        self, source_type: str, source_id: str, target_type: str, target_id: str, *,
        max_depth: int = 3, max_paths: int = 20, max_nodes: int = 200,
        relationship_types: list[str] | None = None, as_of: str | None = None,
        include_history: bool = False, include_private: bool = False,
    ) -> dict[str, Any]:
        max_depth, max_paths, max_nodes = max(1, min(max_depth, 3)), max(1, min(max_paths, 20)), max(2, min(max_nodes, 500))
        started = time.monotonic()
        with db_connection(self.db_path) as conn:
            source_id = _active_redirect(conn, source_type, source_id) or source_id
            target_id = _active_redirect(conn, target_type, target_id) or target_id
            clauses = ["review_status='approved'"]
            params: list[Any] = []
            if not include_private:
                clauses.append("visibility IN ('public','internal')")
            if not include_history and not as_of:
                clauses.append("is_current=1")
            if relationship_types:
                clauses.append("relationship_type IN (%s)" % ",".join("?" * len(relationship_types)))
                params.extend(relationship_types)
            rows = [dict(row) for row in conn.execute("SELECT * FROM p3_canonical_relationships WHERE " + " AND ".join(clauses), params)]
        if as_of:
            point = _parse_date(as_of)
            rows = [row for row in rows if (_parse_date(row["valid_from"]) or date.min) <= point <= (_parse_date(row["valid_to"]) or date.max)]
        adjacency: dict[tuple[str, str], list[tuple[tuple[str, str], dict[str, Any]]]] = {}
        for row in rows:
            left, right = (row["subject_type"], row["subject_id"]), (row["object_type"], row["object_id"])
            adjacency.setdefault(left, []).append((right, row)); adjacency.setdefault(right, []).append((left, row))
        start, goal = (source_type, source_id), (target_type, target_id)
        queue = deque([(start, [start], [])]); paths: list[dict[str, Any]] = []; visited_nodes = {start}; truncated = False
        while queue and len(paths) < max_paths:
            node, nodes, edges = queue.popleft()
            if len(edges) >= max_depth:
                continue
            for neighbor, edge in adjacency.get(node, []):
                if neighbor in nodes:
                    continue
                if len(visited_nodes) >= max_nodes or time.monotonic() - started > .75:
                    truncated = True; queue.clear(); break
                visited_nodes.add(neighbor)
                new_nodes, new_edges = nodes + [neighbor], edges + [edge]
                if neighbor == goal:
                    confidence = min(int(item["confidence"]) for item in new_edges)
                    paths.append({"nodes": [{"type": n[0], "id": n[1]} for n in new_nodes], "edges": new_edges, "hops": len(new_edges), "confidence": confidence})
                else:
                    queue.append((neighbor, new_nodes, new_edges))
        paths.sort(key=lambda item: (item["hops"], -item["confidence"]))
        return {"source": {"type": source_type, "id": source_id}, "target": {"type": target_type, "id": target_id},
                "paths": paths, "limits": {"max_depth": max_depth, "max_paths": max_paths, "max_nodes": max_nodes},
                "visited_nodes": len(visited_nodes), "truncated": truncated, "elapsed_ms": int((time.monotonic() - started) * 1000)}

    def graph(self, entity_type: str, entity_id: str, *, depth: int = 2, max_nodes: int = 100, include_private: bool = False) -> dict[str, Any]:
        depth = max(1, min(depth, 3)); max_nodes = max(2, min(max_nodes, 200))
        with db_connection(self.db_path) as conn:
            clauses = ["review_status='approved'", "is_current=1"]
            if not include_private:
                clauses.append("visibility IN ('public','internal')")
            rows = [dict(row) for row in conn.execute("SELECT * FROM p3_canonical_relationships WHERE " + " AND ".join(clauses))]
        start = (entity_type, entity_id); seen = {start}; frontier = {start}; selected: dict[int, dict[str, Any]] = {}
        for _ in range(depth):
            next_frontier = set()
            for row in rows:
                left, right = (row["subject_type"], row["subject_id"]), (row["object_type"], row["object_id"])
                if left in frontier or right in frontier:
                    selected[int(row["id"])] = row
                    other = right if left in frontier else left
                    if other not in seen and len(seen) < max_nodes:
                        seen.add(other); next_frontier.add(other)
            frontier = next_frontier
        return {"center": {"type": entity_type, "id": entity_id}, "nodes": [{"type": item[0], "id": item[1]} for item in sorted(seen)], "edges": list(selected.values()), "truncated": len(seen) >= max_nodes}


class ConnectionRecommendationService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else resolved_db_path()

    def recommend(self, source_person_id: str, *, limit: int = 10, actor: str = "system", persist: bool = False, is_pilot: bool = False, pilot_batch_id: str | None = None) -> list[dict[str, Any]]:
        network = RelationshipNetworkService(self.db_path)
        with db_connection(self.db_path) as conn:
            people = [str(row[0]) for row in conn.execute("SELECT external_id FROM people WHERE external_id<>? AND COALESCE(is_active,1)=1", (source_person_id,))]
        recommendations = []
        for person_id in people:
            result = network.find_paths("person", source_person_id, "person", person_id, max_depth=3, max_paths=2)
            if any(path["hops"] == 1 for path in result["paths"]):
                continue
            usable = [path for path in result["paths"] if path["hops"] >= 2 and all(edge["evidence_status"] == "evidence_backed" for edge in path["edges"])]
            if not usable:
                continue
            best = usable[0]
            recommendations.append({"recommended_person_id": person_id, "confidence": best["confidence"], "reason": {"hops": best["hops"], "relationship_types": [edge["relationship_type"] for edge in best["edges"]]}, "path": best, "risk_note": "仅供人工研判，不代表联系授权"})
        recommendations.sort(key=lambda item: (-item["confidence"], item["path"]["hops"]))
        recommendations = recommendations[:max(1, min(limit, 20))]
        if persist:
            with db_connection(self.db_path) as conn:
                for item in recommendations:
                    ts = now_iso()
                    conn.execute(
                        """INSERT INTO p3_connection_candidates(candidate_no,source_person_id,recommended_person_id,reason_json,path_json,evidence_json,confidence,risk_note,status,is_pilot,pilot_batch_id,created_by,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,'candidate',?,?,?,?,?)""",
                        (f"CC-{uuid.uuid4().hex[:12].upper()}", source_person_id, item["recommended_person_id"],
                         json.dumps(item["reason"], ensure_ascii=False), json.dumps(item["path"], ensure_ascii=False, default=str),
                         json.dumps([edge["id"] for edge in item["path"]["edges"]]), item["confidence"], item["risk_note"],
                         int(is_pilot), pilot_batch_id, actor, ts, ts),
                    )
        return recommendations


def list_relationship_candidates(db_path: str | Path | None = None, status: str = "") -> list[dict[str, Any]]:
    with db_connection(db_path or resolved_db_path()) as conn:
        sql, params = "SELECT * FROM p3_relationship_candidates", ()
        if status:
            sql += " WHERE status=?"; params = (status,)
        return [dict(row) for row in conn.execute(sql + " ORDER BY id DESC", params)]


def list_relationship_types(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with db_connection(db_path or resolved_db_path()) as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM p3_relationship_type_registry WHERE active=1 ORDER BY category,relationship_type")]
