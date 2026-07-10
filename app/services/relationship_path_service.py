from __future__ import annotations

import sqlite3
from collections import deque
from typing import Any


SUBJECT_TABLES = {
    "organization": ("organizations", "standard_name", "企业/机构", "/subjects/organization/{external_id}"),
    "person": ("people", "name", "人物", "/subjects/person/{external_id}"),
    "project": ("projects", "name", "项目", "/subjects/project/{external_id}"),
}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone()
    return bool(row)


def resolve_subject(
    conn: sqlite3.Connection, subject_type: str, subject_id: str | int
) -> dict[str, Any] | None:
    normalized = (subject_type or "").strip().lower()
    config = SUBJECT_TABLES.get(normalized)
    if not config:
        return None
    table, label_col, type_label, url_tpl = config
    row = conn.execute(
        f"SELECT * FROM {table} WHERE external_id=? OR CAST(id AS TEXT)=? LIMIT 1",
        (str(subject_id), str(subject_id)),
    ).fetchone()
    if not row:
        return None
    external_id = row["external_id"]
    return {
        "type": normalized,
        "type_label": type_label,
        "id": row["id"],
        "external_id": external_id,
        "name": row[label_col],
        "profile_url": url_tpl.format(external_id=external_id),
        "is_active": bool(row["is_active"]) if "is_active" in row.keys() else True,
    }


def resolve_external_id(conn: sqlite3.Connection, external_id: str) -> dict[str, Any]:
    for subject_type, (table, label_col, type_label, url_tpl) in SUBJECT_TABLES.items():
        row = conn.execute(
            f"SELECT id, external_id, {label_col} AS display_name, is_active FROM {table} WHERE external_id=? LIMIT 1",
            (external_id,),
        ).fetchone()
        if row:
            return {
                "type": subject_type,
                "type_label": type_label,
                "id": row["id"],
                "external_id": row["external_id"],
                "name": row["display_name"],
                "profile_url": url_tpl.format(external_id=row["external_id"]),
                "is_active": bool(row["is_active"]),
            }
    return {
        "type": "unknown",
        "type_label": "其他主体",
        "id": None,
        "external_id": external_id,
        "name": external_id,
        "profile_url": "",
        "is_active": True,
    }


def qbay_member_anchors(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    if not table_exists(conn, "v04f_club_memberships"):
        return {}
    rows = conn.execute(
        """
        SELECT
          m.id AS membership_id,
          m.member_no,
          m.member_level,
          p.external_id AS person_external_id,
          p.name AS person_name,
          o.external_id AS organization_external_id,
          o.standard_name AS organization_name
        FROM v04f_club_memberships m
        JOIN people p ON p.id=m.person_id
        LEFT JOIN organizations o ON o.id=m.organization_id
        WHERE m.status='active'
        """
    ).fetchall()
    anchors: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        member = {
            "membership_id": row["membership_id"],
            "member_no": row["member_no"],
            "member_level": row["member_level"],
            "person_external_id": row["person_external_id"],
            "person_name": row["person_name"],
            "organization_external_id": row["organization_external_id"],
            "organization_name": row["organization_name"],
        }
        anchors.setdefault(row["person_external_id"], []).append(member)
        if row["organization_external_id"]:
            anchors.setdefault(row["organization_external_id"], []).append(member)
    return anchors


def _relation_graph(conn: sqlite3.Connection) -> dict[str, list[dict[str, str]]]:
    if not table_exists(conn, "relations"):
        return {}
    rows = conn.execute(
        """
        SELECT source_external_id, target_external_id, relation_type, external_id
        FROM relations
        WHERE COALESCE(is_active,1)=1
          AND source_external_id IS NOT NULL
          AND target_external_id IS NOT NULL
        """
    ).fetchall()
    graph: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        source = row["source_external_id"]
        target = row["target_external_id"]
        relation_type = row["relation_type"] or "关联"
        relation_no = row["external_id"] or ""
        graph.setdefault(source, []).append(
            {
                "to": target,
                "relation_type": relation_type,
                "direction": "out",
                "relation_no": relation_no,
            }
        )
        graph.setdefault(target, []).append(
            {
                "to": source,
                "relation_type": relation_type,
                "direction": "in",
                "relation_no": relation_no,
            }
        )
    return graph


def find_qbay_paths(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str | int,
    *,
    max_edges: int = 3,
    max_paths: int = 20,
) -> dict[str, Any]:
    subject = resolve_subject(conn, subject_type, subject_id)
    if not subject:
        return {"subject": None, "paths": [], "anchor_count": 0}

    anchors = qbay_member_anchors(conn)
    graph = _relation_graph(conn)
    start = subject["external_id"]
    paths: list[dict[str, Any]] = []
    seen_path_keys: set[tuple[str, ...]] = set()

    if start in anchors:
        for member in anchors[start]:
            paths.append(
                {
                    "nodes": [resolve_external_id(conn, start)],
                    "edges": [],
                    "member": member,
                    "edge_count": 0,
                    "summary": f"目标主体本身已关联 Q-BAY 会员 {member['person_name']}。",
                }
            )
            if len(paths) >= max_paths:
                return {"subject": subject, "paths": paths, "anchor_count": len(anchors)}

    queue: deque[tuple[str, list[str], list[dict[str, str]]]] = deque()
    queue.append((start, [start], []))
    best_depth: dict[str, int] = {start: 0}

    while queue and len(paths) < max_paths:
        current, node_ids, edge_rows = queue.popleft()
        depth = len(edge_rows)
        if depth >= max_edges:
            continue
        for edge in graph.get(current, []):
            nxt = edge["to"]
            if nxt in node_ids:
                continue
            new_nodes = [*node_ids, nxt]
            new_edges = [*edge_rows, edge]
            new_depth = len(new_edges)

            if nxt in anchors:
                for member in anchors[nxt]:
                    key = tuple(new_nodes + [member["member_no"]])
                    if key in seen_path_keys:
                        continue
                    seen_path_keys.add(key)
                    nodes = [resolve_external_id(conn, value) for value in new_nodes]
                    display_edges = []
                    for row in new_edges:
                        display_edges.append(
                            {
                                "relation_type": row["relation_type"],
                                "direction": row["direction"],
                                "direction_label": "正向" if row["direction"] == "out" else "反向",
                                "relation_no": row["relation_no"],
                            }
                        )
                    names = " → ".join(node["name"] for node in nodes)
                    paths.append(
                        {
                            "nodes": nodes,
                            "edges": display_edges,
                            "member": member,
                            "edge_count": new_depth,
                            "summary": f"{names}，可通过会员 {member['person_name']} 切入。",
                        }
                    )
                    if len(paths) >= max_paths:
                        break

            if new_depth < max_edges and new_depth <= best_depth.get(nxt, max_edges + 1):
                best_depth[nxt] = new_depth
                queue.append((nxt, new_nodes, new_edges))

    paths.sort(key=lambda item: (item["edge_count"], item["member"]["member_no"]))
    return {"subject": subject, "paths": paths[:max_paths], "anchor_count": len(anchors)}


def path_to_template_parts(path: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    nodes = path.get("nodes") or []
    edges = path.get("edges") or []
    for index, node in enumerate(nodes):
        parts.append({"kind": "node", **node})
        if index < len(edges):
            edge = edges[index]
            prefix = "" if edge.get("direction") == "out" else "反向·"
            parts.append(
                {
                    "kind": "edge",
                    "label": prefix + str(edge.get("relation_type") or "关联"),
                    "relation_no": edge.get("relation_no") or "",
                }
            )
    return parts
