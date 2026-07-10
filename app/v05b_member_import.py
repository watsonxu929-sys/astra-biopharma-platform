from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
import httpx

from app.security import can, current_username
from app.services.member_import_service import (
    CANONICAL_FIELDS,
    MAX_UPLOAD_BYTES,
    SUPPORTED_DOCUMENTS,
    SUPPORTED_IMAGES,
    clean_text,
    download_public_image,
    fetch_web_image_candidates,
    field_labels,
    normalize_and_store_image,
    parse_text,
    parse_uploaded_document,
    validate_draft,
)
from app.v04c_review import db_connection, default_db_path
from app.v04f_operations import ensure_schema as ensure_v04f_schema
from scripts.migrate_v05b import SCHEMA_SQL

router = APIRouter(tags=["v0.5B Q-BAY 会员智能导入与头像"])
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STORAGE_ROOT = PROJECT_ROOT / "data" / "uploads" / "v05b" / "assets"
TEMP_ROOT = PROJECT_ROOT / "data" / "uploads" / "v05b" / "temp"
MAX_DRAFTS_PER_JOB = 300
V05C_DRAFT_COLUMNS = {
    "source_structure": "TEXT",
    "field_confidence_json": "TEXT",
    "field_evidence_json": "TEXT",
    "quality_flags_json": "TEXT",
    "manually_confirmed_fields": "TEXT",
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None) -> Path:
    ensure_v04f_schema(db_path)
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(v05b_import_drafts)").fetchall()}
        for column, ddl in V05C_DRAFT_COLUMNS.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE v05b_import_drafts ADD COLUMN {column} {ddl}")
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return path


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (json.JSONDecodeError, TypeError):
        return default


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now_iso()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def _next_subject_id(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    stem = f"{prefix}-{stamp}-"
    rows = conn.execute(f"SELECT external_id FROM {table} WHERE external_id LIKE ?", (f"{stem}%",)).fetchall()
    maximum = 0
    for row in rows:
        tail = str(row[0] or "").replace(stem, "", 1)
        if tail.isdigit():
            maximum = max(maximum, int(tail))
    return f"{stem}{maximum + 1:06d}"


def _render(request: Request, mode: str, **context: Any):
    return TEMPLATES.TemplateResponse(
        request=request,
        name="v05b_member_import.html",
        context={"mode": mode, "field_labels": field_labels(), **context},
    )


def _require_manage_club(request: Request) -> None:
    if not can(request, "manage_club"):
        raise HTTPException(403, "当前账号没有会员导入权限")


def _create_job(
    conn: sqlite3.Connection,
    *,
    import_type: str,
    original_filename: str = "",
    source_url: str = "",
    raw_text: str = "",
    created_by: str,
) -> sqlite3.Row:
    ts = now_iso()
    job_no = _next_no(conn, "QBI")
    cur = conn.execute(
        """
        INSERT INTO v05b_import_jobs(
          job_no,import_type,original_filename,source_url,raw_text,status,
          created_by,created_at,updated_at
        ) VALUES (?,?,?,?,?,'reviewing',?,?,?)
        """,
        (job_no, import_type, original_filename or None, source_url or None, raw_text or None, created_by, ts, ts),
    )
    return conn.execute("SELECT * FROM v05b_import_jobs WHERE id=?", (cur.lastrowid,)).fetchone()


def _insert_asset(
    conn: sqlite3.Connection,
    *,
    data: bytes,
    original_filename: str,
    source_type: str,
    job_id: int | None = None,
    draft_id: int | None = None,
    membership_id: int | None = None,
    person_id: int | None = None,
    source_url: str = "",
    source_title: str = "",
    source_locator: str = "",
    actor: str = "",
) -> int:
    stored = normalize_and_store_image(data, storage_root=STORAGE_ROOT, preferred_name=original_filename or "avatar")
    existing = conn.execute(
        """
        SELECT id FROM v05b_media_assets
        WHERE sha256=? AND COALESCE(job_id,0)=COALESCE(?,0)
          AND COALESCE(draft_id,0)=COALESCE(?,0)
          AND COALESCE(membership_id,0)=COALESCE(?,0)
          AND is_active=1
        LIMIT 1
        """,
        (stored["sha256"], job_id, draft_id, membership_id),
    ).fetchone()
    if existing:
        return int(existing["id"])
    ts = now_iso()
    asset_no = _next_no(conn, "QBAI")
    cur = conn.execute(
        """
        INSERT INTO v05b_media_assets(
          asset_no,job_id,draft_id,membership_id,person_id,asset_type,original_filename,
          stored_filename,mime_type,size_bytes,width,height,source_type,source_url,
          source_title,source_locator,sha256,confirmed_by,created_at,updated_at
        ) VALUES (?,?,?,?,?,'avatar',?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            asset_no,
            job_id,
            draft_id,
            membership_id,
            person_id,
            original_filename,
            stored["stored_filename"],
            stored["mime_type"],
            stored["size_bytes"],
            stored["width"],
            stored["height"],
            source_type,
            source_url or None,
            source_title or None,
            source_locator or None,
            stored["sha256"],
            actor or None,
            ts,
            ts,
        ),
    )
    return int(cur.lastrowid)


def _create_job_drafts(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    drafts: list[dict[str, Any]],
    images: list[dict[str, Any]],
    actor: str,
) -> None:
    if not drafts:
        raise ValueError("未识别到可导入的会员记录。")
    if len(drafts) > MAX_DRAFTS_PER_JOB:
        raise ValueError(f"单次最多导入 {MAX_DRAFTS_PER_JOB} 条，请拆分文件后重试。")
    draft_ids: list[int] = []
    ts = now_iso()
    for idx, draft in enumerate(drafts, start=1):
        warnings = list(draft.get("warnings") or []) + validate_draft(draft)
        cur = conn.execute(
            """
            INSERT INTO v05b_import_drafts(
              job_id,row_no,source_locator,name,organization_name,title,mobile,email,wechat,city,
              industry_tags,expertise_tags,offered_resources,cooperation_needs,self_introduction,
              referral_source,referrer_name,preferred_contact_method,member_level,member_status,owner,
              source_text,source_structure,field_confidence_json,field_evidence_json,quality_flags_json,
              warnings_json,selected,status,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,'draft',?,?)
            """,
            (
                job["id"],
                idx,
                clean_text(draft.get("source_locator")),
                clean_text(draft.get("name")),
                clean_text(draft.get("organization_name")),
                clean_text(draft.get("title")),
                clean_text(draft.get("mobile")),
                clean_text(draft.get("email")),
                clean_text(draft.get("wechat")),
                clean_text(draft.get("city")),
                clean_text(draft.get("industry_tags")),
                clean_text(draft.get("expertise_tags")),
                clean_text(draft.get("offered_resources")),
                clean_text(draft.get("cooperation_needs")),
                clean_text(draft.get("self_introduction")),
                clean_text(draft.get("referral_source")),
                clean_text(draft.get("referrer_name")),
                clean_text(draft.get("preferred_contact_method")),
                clean_text(draft.get("member_level")) or "standard",
                clean_text(draft.get("member_status")) or "active",
                clean_text(draft.get("owner")) or actor,
                clean_text(draft.get("source_text")),
                clean_text(draft.get("source_structure")) or "unrecognized",
                _json(draft.get("field_confidence") or {}),
                _json(draft.get("field_evidence") or {}),
                _json(draft.get("quality_flags") or []),
                _json(warnings),
                ts,
                ts,
            ),
        )
        draft_ids.append(int(cur.lastrowid))

    for image in images:
        target_index = image.get("draft_index")
        draft_id = draft_ids[target_index] if isinstance(target_index, int) and 0 <= target_index < len(draft_ids) else None
        try:
            asset_id = _insert_asset(
                conn,
                data=image["bytes"],
                original_filename=image.get("filename") or "embedded-avatar",
                source_type="document_embedded",
                job_id=int(job["id"]),
                draft_id=draft_id,
                source_locator=image.get("source_locator") or "",
                actor=actor,
            )
        except ValueError:
            continue
        if draft_id:
            conn.execute(
                "UPDATE v05b_import_drafts SET image_asset_id=COALESCE(image_asset_id,?),updated_at=? WHERE id=?",
                (asset_id, ts, draft_id),
            )
    conn.execute(
        "UPDATE v05b_import_jobs SET total_count=?,selected_count=?,updated_at=? WHERE id=?",
        (len(draft_ids), len(draft_ids), ts, job["id"]),
    )


def _duplicate_info(conn: sqlite3.Connection, draft: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(draft)
    mobile = re.sub(r"\D", "", data.get("mobile") or "")
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    org_name = (data.get("organization_name") or "").strip()
    membership = None
    if mobile or email:
        clauses = []
        params: list[Any] = []
        if mobile:
            clauses.append("REPLACE(REPLACE(REPLACE(c.mobile,' ',''),'-',''),'+86','')=?")
            params.append(mobile[-11:])
        if email:
            clauses.append("lower(c.email)=?")
            params.append(email)
        membership = conn.execute(
            f"""
            SELECT m.id AS membership_id,m.member_no,m.person_id,m.organization_id,m.status,
                   p.name AS person_name,o.standard_name AS organization_name
            FROM v05b_member_contacts c
            JOIN v04f_club_memberships m ON m.id=c.membership_id
            JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE ({' OR '.join(clauses)}) AND m.status IN ('pending','active','suspended')
            ORDER BY m.id DESC LIMIT 1
            """,
            params,
        ).fetchone()
    if not membership and name:
        params = [name]
        org_clause = ""
        if org_name:
            org_clause = " AND lower(COALESCE(o.standard_name,''))=lower(?)"
            params.append(org_name)
        membership = conn.execute(
            f"""
            SELECT m.id AS membership_id,m.member_no,m.person_id,m.organization_id,m.status,
                   p.name AS person_name,o.standard_name AS organization_name
            FROM v04f_club_memberships m
            JOIN people p ON p.id=m.person_id
            LEFT JOIN organizations o ON o.id=m.organization_id
            WHERE lower(p.name)=lower(?) {org_clause}
              AND m.status IN ('pending','active','suspended')
            ORDER BY m.id DESC LIMIT 1
            """,
            params,
        ).fetchone()
    people = []
    if name:
        people = [dict(row) for row in conn.execute(
            "SELECT id,external_id,name,public_role,organization_network FROM people WHERE lower(name)=lower(?) AND is_active=1 LIMIT 8",
            (name,),
        ).fetchall()]
    organizations = []
    if org_name:
        organizations = [dict(row) for row in conn.execute(
            "SELECT id,external_id,standard_name,org_type,region FROM organizations WHERE lower(standard_name)=lower(?) AND is_active=1 LIMIT 8",
            (org_name,),
        ).fetchall()]
    return {
        "existing_membership": dict(membership) if membership else None,
        "people": people,
        "organizations": organizations,
        "high_risk": bool(membership),
    }


def _job_context(conn: sqlite3.Connection, job_id: int) -> dict[str, Any]:
    job = conn.execute("SELECT * FROM v05b_import_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        raise HTTPException(404, "导入任务不存在")
    draft_rows = conn.execute("SELECT * FROM v05b_import_drafts WHERE job_id=? ORDER BY row_no", (job_id,)).fetchall()
    drafts: list[dict[str, Any]] = []
    for row in draft_rows:
        item = dict(row)
        if item["status"] in {"draft", "ready", "failed"}:
            duplicate = _duplicate_info(conn, row)
            warnings = list(dict.fromkeys(_load_json(item.get("warnings_json"), []) + validate_draft(item)))
            item["duplicate"] = duplicate
            item["warnings"] = warnings
            conn.execute(
                "UPDATE v05b_import_drafts SET duplicate_json=?,warnings_json=?,updated_at=? WHERE id=?",
                (_json(duplicate), _json(warnings), now_iso(), item["id"]),
            )
        else:
            item["duplicate"] = _load_json(item.get("duplicate_json"), {})
            item["warnings"] = _load_json(item.get("warnings_json"), [])
        drafts.append(item)
    images = [dict(row) for row in conn.execute(
        "SELECT * FROM v05b_media_assets WHERE job_id=? AND is_active=1 ORDER BY id", (job_id,)
    ).fetchall()]
    web_images = [dict(row) for row in conn.execute(
        "SELECT * FROM v05b_web_image_candidates WHERE job_id=? ORDER BY status,id", (job_id,)
    ).fetchall()]
    return {"job": dict(job), "drafts": drafts, "images": images, "web_images": web_images}


@router.get("/club/import", response_class=HTMLResponse)
def import_home(request: Request, message: str = Query(""), error: str = Query("")):
    _require_manage_club(request)
    ensure_schema()
    with db_connection() as conn:
        jobs = [dict(row) for row in conn.execute(
            "SELECT * FROM v05b_import_jobs ORDER BY id DESC LIMIT 30"
        ).fetchall()]
    return _render(request, "home", jobs=jobs, message=message, error=error)


@router.post("/club/import/text")
def import_text(request: Request, raw_text: str = Form(...), source_url: str = Form("")):
    _require_manage_club(request)
    ensure_schema()
    try:
        drafts = parse_text(raw_text, locator_prefix="粘贴文本")
        with db_connection() as conn:
            job = _create_job(
                conn,
                import_type="paste",
                source_url=source_url,
                raw_text=raw_text[:200_000],
                created_by=current_username(request),
            )
            _create_job_drafts(conn, job, drafts, [], current_username(request))
        return RedirectResponse(f"/club/import/jobs/{job['id']}", status_code=303)
    except ValueError as exc:
        return RedirectResponse(f"/club/import?error={str(exc)}", status_code=303)


@router.post("/club/import/file")
async def import_file(request: Request, file: UploadFile = File(...)):
    _require_manage_club(request)
    ensure_schema()
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENTS and suffix != ".doc":
        return RedirectResponse("/club/import?error=文件格式不支持", status_code=303)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return RedirectResponse("/club/import?error=文件超过20MB", status_code=303)
    temp_path = TEMP_ROOT / f"{datetime.now():%Y%m%d%H%M%S%f}_{filename}"
    temp_path.write_bytes(data)
    try:
        drafts, images = parse_uploaded_document(temp_path)
        with db_connection() as conn:
            job = _create_job(
                conn,
                import_type=suffix.lstrip(".") or "file",
                original_filename=filename,
                created_by=current_username(request),
            )
            _create_job_drafts(conn, job, drafts, images, current_username(request))
        return RedirectResponse(f"/club/import/jobs/{job['id']}", status_code=303)
    except (ValueError, OSError) as exc:
        return RedirectResponse(f"/club/import?error={str(exc)}", status_code=303)
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/club/import/template.xlsx")
def download_template(request: Request):
    _require_manage_club(request)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Q-BAY会员导入"
    headers = [field_labels()[field] for field in CANONICAL_FIELDS]
    sheet.append(headers)
    sheet.append([
        "张三", "示例生物科技", "BD负责人", "13800000000", "demo@example.com", "demo_wechat",
        "上海", "创新药;生物技术", "商务拓展;融资", "产业资源;投资机构", "融资;园区落地",
        "示例会员简介", "活动报名", "李四", "微信", "standard", "active", "运营A",
    ])
    sheet.freeze_panes = "A2"
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 18
    output = BytesIO()
    workbook.save(output)
    return Response(
        output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="qbay_member_import_template.xlsx"'},
    )


@router.get("/club/import/jobs/{job_id}", response_class=HTMLResponse)
def import_job(request: Request, job_id: int, message: str = Query(""), error: str = Query("")):
    _require_manage_club(request)
    ensure_schema()
    with db_connection() as conn:
        context = _job_context(conn, job_id)
    return _render(request, "job", **context, message=message, error=error)


def _form_text(form: Any, key: str, fallback: str = "") -> str:
    return clean_text(form.get(key, fallback))


@router.post("/club/import/jobs/{job_id}/save")
async def save_import_job(request: Request, job_id: int):
    _require_manage_club(request)
    ensure_schema()
    form = await request.form()
    actor = current_username(request)
    saved = skipped = failed = selected_count = 0
    errors: list[str] = []
    with db_connection() as conn:
        job = conn.execute("SELECT * FROM v05b_import_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "导入任务不存在")
        rows = conn.execute("SELECT * FROM v05b_import_drafts WHERE job_id=? ORDER BY row_no", (job_id,)).fetchall()
        for row in rows:
            draft_id = int(row["id"])
            selected = form.get(f"selected_{draft_id}") == "1"
            fields = {field: _form_text(form, f"{field}_{draft_id}", row[field] or "") for field in CANONICAL_FIELDS}
            duplicate_action = _form_text(form, f"duplicate_action_{draft_id}", "skip")
            existing_person_id = int(_form_text(form, f"existing_person_id_{draft_id}", "0") or 0)
            existing_org_id = int(_form_text(form, f"existing_org_id_{draft_id}", "0") or 0)
            conn.execute(
                """
                UPDATE v05b_import_drafts SET
                  name=?,organization_name=?,title=?,mobile=?,email=?,wechat=?,city=?,industry_tags=?,
                  expertise_tags=?,offered_resources=?,cooperation_needs=?,self_introduction=?,referral_source=?,
                  referrer_name=?,preferred_contact_method=?,member_level=?,member_status=?,owner=?,selected=?,updated_at=?
                WHERE id=?
                """,
                (
                    fields["name"], fields["organization_name"], fields["title"], fields["mobile"], fields["email"], fields["wechat"],
                    fields["city"], fields["industry_tags"], fields["expertise_tags"], fields["offered_resources"],
                    fields["cooperation_needs"], fields["self_introduction"], fields["referral_source"], fields["referrer_name"],
                    fields["preferred_contact_method"], fields["member_level"] or "standard", fields["member_status"] or "active",
                    fields["owner"] or actor, 1 if selected else 0, now_iso(), draft_id,
                ),
            )
            if not selected:
                continue
            selected_count += 1
            current = conn.execute("SELECT * FROM v05b_import_drafts WHERE id=?", (draft_id,)).fetchone()
            warnings = validate_draft(dict(current))
            fatal = [
                item
                for item in warnings
                if "不能为空" in item
                or "栏目名称" in item
                or "疑似多人" in item
                or "姓名疑似" in item
                or "姓名包含" in item
                or "姓名置信度" in item
            ]
            if fatal:
                failed += 1
                message = "；".join(fatal)
                conn.execute("UPDATE v05b_import_drafts SET status='failed',error_message=?,updated_at=? WHERE id=?", (message, now_iso(), draft_id))
                errors.append(f"第{row['row_no']}条：{message}")
                continue
            duplicate = _duplicate_info(conn, current)
            existing_membership = duplicate.get("existing_membership")
            if existing_membership and duplicate_action == "skip":
                skipped += 1
                conn.execute("UPDATE v05b_import_drafts SET status='skipped',error_message='检测到现有有效会员，已按选择跳过',updated_at=? WHERE id=?", (now_iso(), draft_id))
                continue
            try:
                if existing_membership and duplicate_action == "link":
                    membership_id = int(existing_membership["membership_id"])
                    person_id = int(existing_membership["person_id"])
                    organization_id = int(existing_membership["organization_id"] or 0)
                    _fill_existing_membership(conn, membership_id, current, job_id)
                else:
                    person_id, organization_id, membership_id = _save_new_membership(
                        conn,
                        current,
                        job,
                        actor,
                        existing_person_id=existing_person_id,
                        existing_org_id=existing_org_id,
                    )
                if current["image_asset_id"]:
                    _bind_asset(conn, int(current["image_asset_id"]), membership_id, person_id, actor)
                conn.execute(
                    """
                    UPDATE v05b_import_drafts SET status='saved',saved_person_id=?,saved_organization_id=?,
                      saved_membership_id=?,error_message=NULL,updated_at=? WHERE id=?
                    """,
                    (person_id, organization_id or None, membership_id, now_iso(), draft_id),
                )
                saved += 1
            except (ValueError, sqlite3.Error) as exc:
                failed += 1
                message = str(exc)[:500]
                conn.execute("UPDATE v05b_import_drafts SET status='failed',error_message=?,updated_at=? WHERE id=?", (message, now_iso(), draft_id))
                errors.append(f"第{row['row_no']}条：{message}")
        status = "completed" if failed == 0 else ("partially_saved" if saved else "failed")
        conn.execute(
            """
            UPDATE v05b_import_jobs SET status=?,selected_count=?,saved_count=?,failed_count=?,
              completed_at=?,updated_at=? WHERE id=?
            """,
            (status, selected_count, saved, failed, now_iso(), now_iso(), job_id),
        )
    message = f"保存完成：成功 {saved}，跳过 {skipped}，失败 {failed}"
    if errors:
        message += "；" + "；".join(errors[:3])
    return RedirectResponse(f"/club/import/jobs/{job_id}?message={message}", status_code=303)


def _fill_existing_membership(conn: sqlite3.Connection, membership_id: int, draft: sqlite3.Row, job_id: int) -> None:
    conn.execute(
        """
        UPDATE v04f_club_memberships SET
          member_role=CASE WHEN COALESCE(member_role,'')='' THEN ? ELSE member_role END,
          industry_tags=CASE WHEN COALESCE(industry_tags,'')='' THEN ? ELSE industry_tags END,
          expertise_tags=CASE WHEN COALESCE(expertise_tags,'')='' THEN ? ELSE expertise_tags END,
          cooperation_preferences=CASE WHEN COALESCE(cooperation_preferences,'')='' THEN ? ELSE cooperation_preferences END,
          updated_at=? WHERE id=?
        """,
        (draft["title"], draft["industry_tags"], draft["expertise_tags"], draft["cooperation_needs"], now_iso(), membership_id),
    )
    _upsert_contact(conn, membership_id, draft, job_id)


def _save_new_membership(
    conn: sqlite3.Connection,
    draft: sqlite3.Row,
    job: sqlite3.Row,
    actor: str,
    *,
    existing_person_id: int = 0,
    existing_org_id: int = 0,
) -> tuple[int, int, int]:
    ts = now_iso()
    organization_id = existing_org_id
    organization_external_id = ""
    if organization_id:
        org = conn.execute("SELECT id,external_id FROM organizations WHERE id=? AND is_active=1", (organization_id,)).fetchone()
        if not org:
            raise ValueError("选择的现有机构不存在")
        organization_external_id = org["external_id"]
    elif draft["organization_name"]:
        exact = conn.execute(
            "SELECT id,external_id FROM organizations WHERE lower(standard_name)=lower(?) AND is_active=1 ORDER BY id LIMIT 2",
            (draft["organization_name"],),
        ).fetchall()
        if len(exact) == 1:
            organization_id = int(exact[0]["id"])
            organization_external_id = exact[0]["external_id"]
        elif len(exact) > 1:
            raise ValueError("存在多家同名机构，请在草稿中明确选择现有机构后再保存")
        else:
            organization_external_id = _next_subject_id(conn, "organizations", "ORG")
            cur = conn.execute(
                """
                INSERT INTO organizations(
                  external_id,standard_name,region,industry_tags,resources,needs,relationship_source,
                  visibility,verification_status,source_type,source_title,source_text,captured_at,
                  analyzed_at,model_version,manually_confirmed,is_active,subject_manually_confirmed,created_at
                ) VALUES (?,?,?,?,?,?,?,'内部','待核验','Q-BAY会员导入',?,?,?,?, 'v0.5B',1,1,1,?)
                """,
                (
                    organization_external_id,
                    draft["organization_name"],
                    draft["city"],
                    draft["industry_tags"],
                    draft["offered_resources"],
                    draft["cooperation_needs"],
                    job["job_no"],
                    job["original_filename"] or "会员智能导入",
                    draft["source_text"],
                    ts,
                    ts,
                    ts,
                ),
            )
            organization_id = int(cur.lastrowid)

    person_id = existing_person_id
    person_external_id = ""
    if person_id:
        person = conn.execute("SELECT id,external_id FROM people WHERE id=? AND is_active=1", (person_id,)).fetchone()
        if not person:
            raise ValueError("选择的现有人物不存在")
        person_external_id = person["external_id"]
    else:
        person_external_id = _next_subject_id(conn, "people", "PER")
        cur = conn.execute(
            """
            INSERT INTO people(
              external_id,name,public_role,organization_network,ability_tags,value_provided,
              relationship_source,visibility,verification_status,source_type,source_title,source_text,
              captured_at,analyzed_at,model_version,manually_confirmed,is_active,subject_manually_confirmed,created_at
            ) VALUES (?,?,?,?,?,?,?,'内部','待核验','Q-BAY会员导入',?,?,?,?, 'v0.5B',1,1,1,?)
            """,
            (
                person_external_id,
                draft["name"],
                draft["title"],
                draft["organization_name"],
                draft["expertise_tags"] or draft["industry_tags"],
                draft["offered_resources"] or draft["self_introduction"],
                job["job_no"],
                job["original_filename"] or "会员智能导入",
                draft["source_text"],
                ts,
                ts,
                ts,
            ),
        )
        person_id = int(cur.lastrowid)

    existing_member = conn.execute(
        "SELECT id FROM v04f_club_memberships WHERE person_id=? AND status IN ('pending','active','suspended')",
        (person_id,),
    ).fetchone()
    if existing_member:
        pass
    member_no = _next_no(conn, "QBM")
    cur = conn.execute(
        """
        INSERT INTO v04f_club_memberships(
          member_no,person_id,organization_id,member_role,member_level,status,joined_at,source,
          owner,industry_tags,expertise_tags,cooperation_preferences,internal_note,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            member_no,
            person_id,
            organization_id or None,
            draft["title"],
            draft["member_level"] or "standard",
            draft["member_status"] or "active",
            ts,
            job["job_no"],
            draft["owner"] or actor,
            draft["industry_tags"],
            draft["expertise_tags"],
            draft["cooperation_needs"],
            f"推荐人：{draft['referrer_name']}；来源：{draft['referral_source']}".strip("；"),
            ts,
            ts,
        ),
    )
    membership_id = int(cur.lastrowid)
    _upsert_contact(conn, membership_id, draft, int(job["id"]))

    if person_external_id and organization_external_id:
        relation = conn.execute(
            """
            SELECT id FROM relations WHERE source_external_id=? AND target_external_id=?
              AND relation_type IN ('任职','任职于','employment') AND is_active=1 LIMIT 1
            """,
            (person_external_id, organization_external_id),
        ).fetchone()
        if not relation:
            conn.execute(
                """
                INSERT INTO relations(
                  external_id,source_external_id,relation_type,target_external_id,evidence_source,
                  visibility,verification_status,source_type,source_title,source_text,captured_at,
                  analyzed_at,model_version,manually_confirmed,is_active,subject_manually_confirmed,created_at
                ) VALUES (?,?, '任职', ?,?,'内部','待核验','Q-BAY会员导入',?,?,?,?, 'v0.5B',1,1,1,?)
                """,
                (
                    _next_subject_id(conn, "relations", "REL"),
                    person_external_id,
                    organization_external_id,
                    job["job_no"],
                    job["original_filename"] or "会员智能导入",
                    draft["source_text"],
                    ts,
                    ts,
                    ts,
                ),
            )

    if draft["cooperation_needs"]:
        conn.execute(
            """
            INSERT INTO v04f_club_needs(
              need_no,membership_id,title,description,need_type,industry_tags,region,urgency,status,created_at,updated_at
            ) VALUES (?,?,'会员导入需求',?,?,?,?,'normal','active',?,?)
            """,
            (_next_no(conn, "QBN"), membership_id, draft["cooperation_needs"], "会员需求", draft["industry_tags"], draft["city"], ts, ts),
        )
    if draft["offered_resources"]:
        conn.execute(
            """
            INSERT INTO v04f_club_offerings(
              offering_no,membership_id,title,description,offering_type,industry_tags,region,availability,status,created_at,updated_at
            ) VALUES (?,?,'会员可提供资源',?,?,?,?,'available','active',?,?)
            """,
            (_next_no(conn, "QBO"), membership_id, draft["offered_resources"], "会员资源", draft["industry_tags"], draft["city"], ts, ts),
        )
    return person_id, organization_id, membership_id


def _upsert_contact(conn: sqlite3.Connection, membership_id: int, draft: sqlite3.Row, job_id: int) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO v05b_member_contacts(
          membership_id,mobile,email,wechat,preferred_contact_method,source_job_id,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(membership_id) DO UPDATE SET
          mobile=CASE WHEN COALESCE(v05b_member_contacts.mobile,'')='' THEN excluded.mobile ELSE v05b_member_contacts.mobile END,
          email=CASE WHEN COALESCE(v05b_member_contacts.email,'')='' THEN excluded.email ELSE v05b_member_contacts.email END,
          wechat=CASE WHEN COALESCE(v05b_member_contacts.wechat,'')='' THEN excluded.wechat ELSE v05b_member_contacts.wechat END,
          preferred_contact_method=CASE WHEN COALESCE(v05b_member_contacts.preferred_contact_method,'')='' THEN excluded.preferred_contact_method ELSE v05b_member_contacts.preferred_contact_method END,
          source_job_id=COALESCE(v05b_member_contacts.source_job_id,excluded.source_job_id),updated_at=excluded.updated_at
        """,
        (
            membership_id,
            draft["mobile"] or None,
            draft["email"] or None,
            draft["wechat"] or None,
            draft["preferred_contact_method"] or None,
            job_id,
            ts,
            ts,
        ),
    )


def _bind_asset(conn: sqlite3.Connection, asset_id: int, membership_id: int, person_id: int, actor: str) -> None:
    conn.execute("UPDATE v05b_media_assets SET is_active=0,deactivated_at=?,updated_at=? WHERE membership_id=? AND id<>? AND is_active=1", (now_iso(), now_iso(), membership_id, asset_id))
    conn.execute(
        "UPDATE v05b_media_assets SET membership_id=?,person_id=?,confirmed_by=?,updated_at=? WHERE id=?",
        (membership_id, person_id, actor, now_iso(), asset_id),
    )


@router.post("/club/import/jobs/{job_id}/drafts/{draft_id}/avatar")
async def upload_draft_avatar(request: Request, job_id: int, draft_id: int, file: UploadFile = File(...)):
    _require_manage_club(request)
    ensure_schema()
    filename = Path(file.filename or "avatar").name
    if Path(filename).suffix.lower() not in SUPPORTED_IMAGES:
        return RedirectResponse(f"/club/import/jobs/{job_id}?error=头像仅支持JPG、PNG、WEBP", status_code=303)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        with db_connection() as conn:
            draft = conn.execute("SELECT * FROM v05b_import_drafts WHERE id=? AND job_id=?", (draft_id, job_id)).fetchone()
            if not draft:
                raise HTTPException(404, "草稿不存在")
            asset_id = _insert_asset(
                conn,
                data=data,
                original_filename=filename,
                source_type="upload",
                job_id=job_id,
                draft_id=draft_id,
                source_locator=draft["source_locator"] or "",
                actor=current_username(request),
            )
            conn.execute("UPDATE v05b_import_drafts SET image_asset_id=?,updated_at=? WHERE id=?", (asset_id, now_iso(), draft_id))
        return RedirectResponse(f"/club/import/jobs/{job_id}?message=头像已上传", status_code=303)
    except ValueError as exc:
        return RedirectResponse(f"/club/import/jobs/{job_id}?error={str(exc)}", status_code=303)


@router.post("/club/import/jobs/{job_id}/web-images")
def collect_web_images(request: Request, job_id: int, source_url: str = Form(...)):
    _require_manage_club(request)
    ensure_schema()
    try:
        title, candidates = fetch_web_image_candidates(source_url)
        with db_connection() as conn:
            if not conn.execute("SELECT 1 FROM v05b_import_jobs WHERE id=?", (job_id,)).fetchone():
                raise HTTPException(404, "导入任务不存在")
            ts = now_iso()
            for candidate in candidates:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO v05b_web_image_candidates(
                      job_id,source_url,image_url,alt_text,status,created_at,updated_at
                    ) VALUES (?,?,?,?,'candidate',?,?)
                    """,
                    (job_id, source_url, candidate["image_url"], candidate["alt_text"], ts, ts),
                )
            conn.execute("UPDATE v05b_import_jobs SET source_url=COALESCE(source_url,?),updated_at=? WHERE id=?", (source_url, ts, job_id))
        return RedirectResponse(f"/club/import/jobs/{job_id}?message=已提取{len(candidates)}张公开图片候选：{title}", status_code=303)
    except (ValueError, httpx.HTTPError) as exc:  # type: ignore[name-defined]
        return RedirectResponse(f"/club/import/jobs/{job_id}?error={str(exc)}", status_code=303)


@router.post("/club/import/jobs/{job_id}/web-images/{candidate_id}/assign")
def assign_web_image(request: Request, job_id: int, candidate_id: int, draft_id: int = Form(...)):
    _require_manage_club(request)
    ensure_schema()
    try:
        with db_connection() as conn:
            candidate = conn.execute("SELECT * FROM v05b_web_image_candidates WHERE id=? AND job_id=?", (candidate_id, job_id)).fetchone()
            draft = conn.execute("SELECT * FROM v05b_import_drafts WHERE id=? AND job_id=?", (draft_id, job_id)).fetchone()
            if not candidate or not draft:
                raise HTTPException(404, "图片候选或草稿不存在")
        data, filename, _ = download_public_image(candidate["image_url"])
        with db_connection() as conn:
            asset_id = _insert_asset(
                conn,
                data=data,
                original_filename=filename,
                source_type="web_capture",
                job_id=job_id,
                draft_id=draft_id,
                source_url=candidate["image_url"],
                source_title=candidate["alt_text"] or "",
                source_locator=draft["source_locator"] or "",
                actor=current_username(request),
            )
            conn.execute("UPDATE v05b_import_drafts SET image_asset_id=?,updated_at=? WHERE id=?", (asset_id, now_iso(), draft_id))
            conn.execute("UPDATE v05b_web_image_candidates SET draft_id=?,local_asset_id=?,status='assigned',updated_at=? WHERE id=?", (draft_id, asset_id, now_iso(), candidate_id))
        return RedirectResponse(f"/club/import/jobs/{job_id}?message=网页头像已绑定到草稿", status_code=303)
    except HTTPException:
        raise
    except (ValueError, httpx.HTTPError, OSError) as exc:
        return RedirectResponse(f"/club/import/jobs/{job_id}?error={str(exc)}", status_code=303)


@router.get("/club/media/{asset_id}")
def member_media(request: Request, asset_id: int, thumb: int = Query(0)):
    ensure_schema()
    with db_connection() as conn:
        asset = conn.execute("SELECT * FROM v05b_media_assets WHERE id=? AND is_active=1", (asset_id,)).fetchone()
    if not asset:
        raise HTTPException(404, "图片不存在")
    relative = Path(asset["stored_filename"])
    if thumb:
        relative = relative.with_name(relative.stem + "_thumb.webp")
    path = (STORAGE_ROOT / relative).resolve()
    if STORAGE_ROOT.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "图片文件不存在")
    return FileResponse(path, media_type="image/webp", filename=None)


@router.post("/club/members/{member_id}/avatar")
async def upload_member_avatar(request: Request, member_id: int, file: UploadFile = File(...)):
    _require_manage_club(request)
    ensure_schema()
    filename = Path(file.filename or "avatar").name
    if Path(filename).suffix.lower() not in SUPPORTED_IMAGES:
        return RedirectResponse(f"/club/members/{member_id}?error=头像仅支持JPG、PNG、WEBP", status_code=303)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        with db_connection() as conn:
            member = conn.execute("SELECT * FROM v04f_club_memberships WHERE id=?", (member_id,)).fetchone()
            if not member:
                raise HTTPException(404, "会员不存在")
            asset_id = _insert_asset(
                conn,
                data=data,
                original_filename=filename,
                source_type="upload",
                membership_id=member_id,
                person_id=int(member["person_id"]),
                actor=current_username(request),
            )
            _bind_asset(conn, asset_id, member_id, int(member["person_id"]), current_username(request))
        return RedirectResponse(f"/club/members/{member_id}?message=头像已更新", status_code=303)
    except ValueError as exc:
        return RedirectResponse(f"/club/members/{member_id}?error={str(exc)}", status_code=303)


@router.get("/v05b/health")
def health():
    path = ensure_schema()
    with db_connection(path) as conn:
        tables = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v05b_%'").fetchone()["c"]
    return {"ok": tables >= 5, "version": "0.5B", "v05b_table_count": tables}
