from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def login(client, username: str, password: str):
    return client.post(
        "/account/login",
        data={"username": username, "password": password, "next": "/private"},
        follow_redirects=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v05a_verify_") as temp:
        db_path = Path(temp) / "security.db"
        os.environ["APP_DB_PATH"] = str(db_path)
        os.environ["APP_SESSION_SECRET"] = "v05a-test-secret-that-is-long-enough"
        os.environ.pop("APP_AUTH_DISABLED", None)

        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.testclient import TestClient

        from app.security import (
            SecurityMiddleware,
            admin_reset_password,
            authenticate_user,
            create_user,
            ensure_security_schema,
            get_user_by_username,
            update_user_admin,
            user_count,
            verify_password,
        )
        from app.v05a_security import router

        ensure_security_schema(db_path)
        app = FastAPI()
        app.add_middleware(SecurityMiddleware)
        app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
        app.include_router(router)

        @app.get("/private", response_class=HTMLResponse)
        def private_page():
            return "private-ok"

        @app.post("/write")
        def write_action():
            return {"ok": True}

        @app.post("/review/test")
        def review_action():
            return {"ok": True}

        @app.get("/club/apply", response_class=HTMLResponse)
        def public_apply():
            return "public-apply"

        client = TestClient(app)
        first = client.get("/private", follow_redirects=False)
        check(first.status_code == 303 and first.headers["location"].startswith("/setup/admin"), "first run redirects to administrator setup")
        check(client.get("/club/apply").status_code == 200, "public club application remains accessible")

        setup = client.post(
            "/setup/admin",
            data={
                "username": "admin",
                "display_name": "系统管理员",
                "password": "SecureAdmin123",
                "confirm_password": "SecureAdmin123",
                "next": "/private",
            },
            follow_redirects=False,
        )
        check(setup.status_code == 303 and setup.headers["location"] == "/private", "first administrator can be created")
        check(user_count(db_path) == 1, "administrator is stored once")
        check(client.get("/private").status_code == 200, "administrator session accesses internal page")
        check(client.post("/write").status_code == 200, "administrator can write data")

        admin = get_user_by_username("admin", db_path)
        check(admin is not None and admin["role"] == "admin", "administrator role is correct")
        check(admin is not None and not verify_password("wrong", admin["password_hash"]), "password is stored as a one-way hash")

        viewer = create_user("viewer1", "只读用户", "ViewerPass123", "viewer", created_by="admin", db_path=db_path)
        reviewer = create_user("reviewer1", "审核用户", "ReviewerPass123", "reviewer", created_by="admin", db_path=db_path)
        operator = create_user("operator1", "运营用户", "OperatorPass123", "operator", created_by="admin", db_path=db_path)
        check(user_count(db_path) == 4, "four role accounts are available")

        viewer_client = TestClient(app)
        check(login(viewer_client, "viewer1", "ViewerPass123").status_code == 303, "viewer can log in")
        check(viewer_client.get("/private").status_code == 200, "viewer can read internal page")
        check(viewer_client.post("/write").status_code == 403, "viewer cannot write data")
        check(viewer_client.post("/review/test").status_code == 403, "viewer cannot review data")

        reviewer_client = TestClient(app)
        check(login(reviewer_client, "reviewer1", "ReviewerPass123").status_code == 303, "reviewer can log in")
        check(reviewer_client.post("/review/test").status_code == 200, "reviewer can process review routes")
        check(reviewer_client.post("/write").status_code == 403, "reviewer cannot modify ordinary business data")

        operator_client = TestClient(app)
        check(login(operator_client, "operator1", "OperatorPass123").status_code == 303, "operator can log in")
        check(operator_client.post("/write").status_code == 200, "operator can modify business data")
        check(operator_client.post("/review/test").status_code == 403, "operator cannot approve review data")

        try:
            update_user_admin(
                int(admin["id"]),
                role="viewer",
                status="active",
                display_name="系统管理员",
                actor_user_id=int(admin["id"]),
                db_path=db_path,
            )
            last_admin_protected = False
        except ValueError:
            last_admin_protected = True
        check(last_admin_protected, "last active administrator cannot be demoted")

        admin_reset_password(int(operator["id"]), "OperatorNew123", db_path=db_path)
        stale = operator_client.get("/private", follow_redirects=False)
        check(stale.status_code == 303 and stale.headers["location"].startswith("/account/login"), "password reset invalidates old sessions")
        reset_user = get_user_by_username("operator1", db_path)
        check(bool(reset_user and reset_user["must_change_password"]), "reset password requires change on next login")

        for _ in range(5):
            authenticate_user("viewer1", "incorrect-password", db_path)
        locked_user, locked_error = authenticate_user("viewer1", "ViewerPass123", db_path)
        check(locked_user is None and "重试" in locked_error, "repeated login failures trigger temporary lockout")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        logs = conn.execute("SELECT * FROM v05a_audit_logs ORDER BY id").fetchall()
        conn.close()
        check({"v05a_users", "v05a_audit_logs"}.issubset(tables), "security tables exist")
        check(len(logs) >= 5, "login and write operations produce audit logs")
        check(all("password" not in str(row["detail_json"] or "").lower() for row in logs), "audit details do not store passwords")

        health = client.get("/v05a/health")
        check(health.status_code == 200 and health.json()["version"] == "v0.5A", "v0.5A health route returns 200")

    print("v0.5A verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
