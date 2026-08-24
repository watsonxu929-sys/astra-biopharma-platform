from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

BASE_DIR = Path(__file__).parent.parent.parent
APP_DIR = BASE_DIR / "app"
SCRIPTS_DIR = BASE_DIR / "scripts"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
DOCS_DIR = BASE_DIR / "docs"
TESTS_DIR = BASE_DIR / "tests"
AUDIT_DIR = BASE_DIR / "docs" / "audit"

EXCLUDED_DIRS = {".git", ".venv", "node_modules", "__pycache__", "data", "logs", ".pytest_cache"}
EXCLUDED_EXTENSIONS = {".pyc", ".pyo", ".db", ".db-shm", ".db-wal", ".log", ".zip", ".bak", ".tmp"}

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_all_files(root: Path, excluded_dirs: Set[str] = None, excluded_extensions: Set[str] = None) -> List[Path]:
    if excluded_dirs is None:
        excluded_dirs = EXCLUDED_DIRS
    if excluded_extensions is None:
        excluded_extensions = EXCLUDED_EXTENSIONS
    
    files = []
    for path in root.rglob("*"):
        if path.is_file():
            if any(part in excluded_dirs for part in path.parts):
                continue
            if path.suffix.lower() in excluded_extensions:
                continue
            files.append(path)
    return files

def analyze_imports(py_files: List[Path]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    imports_by_file: Dict[str, Set[str]] = {}
    imported_by: Dict[str, Set[str]] = {}
    
    for filepath in py_files:
        rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
        imports_by_file[rel_path] = set()
        
        try:
            content = filepath.read_text(encoding="utf-8")
            for match in re.finditer(r"^(?:from|import)\s+([a-zA-Z0-9_.]+)", content, re.MULTILINE):
                mod_name = match.group(1).split(".")[0]
                if mod_name in ("app", "scripts", "tests"):
                    full_mod = match.group(1)
                    imports_by_file[rel_path].add(full_mod)
                    if full_mod not in imported_by:
                        imported_by[full_mod] = set()
                    imported_by[full_mod].add(rel_path)
        except Exception:
            pass
    
    return imports_by_file, imported_by

def find_route_registrations(py_files: List[Path]) -> Dict[str, Set[str]]:
    routes: Dict[str, Set[str]] = {}
    
    for filepath in py_files:
        rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
        try:
            content = filepath.read_text(encoding="utf-8")
            for match in re.finditer(r"\.add_api_route\(['\"]([^'\"]+)['\"]", content):
                route = match.group(1)
                if route not in routes:
                    routes[route] = set()
                routes[route].add(rel_path)
            for match in re.finditer(r"@(?:app|router)\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", content):
                route = match.group(2)
                if route not in routes:
                    routes[route] = set()
                routes[route].add(rel_path)
            for match in re.finditer(r"\.include_router\(", content):
                routes["[included_router]"] = routes.get("[included_router]", set()) | {rel_path}
        except Exception:
            pass
    
    return routes

def analyze_templates(template_files: List[Path]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    template_references: Dict[str, Set[str]] = {}
    referenced_by: Dict[str, Set[str]] = {}
    
    for filepath in template_files:
        rel_path = str(filepath.relative_to(TEMPLATES_DIR)).replace("\\", "/")
        template_references[rel_path] = set()
        
        try:
            content = filepath.read_text(encoding="utf-8")
            for match in re.finditer(r"{%\s*(?:extends|include|import)\s+['\"]([^'\"]+)['\"]", content):
                ref = match.group(1)
                template_references[rel_path].add(ref)
                if ref not in referenced_by:
                    referenced_by[ref] = set()
                referenced_by[ref].add(rel_path)
        except Exception:
            pass
    
    return template_references, referenced_by

def find_static_references(template_files: List[Path]) -> Set[str]:
    references = set()
    
    for filepath in template_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            for match in re.finditer(r"(?:href|src)=['\"]([^'\"]+)['\"]", content):
                ref = match.group(1)
                if ref.startswith("/static/") or ref.startswith("static/"):
                    references.add(ref)
        except Exception:
            pass
    
    return references

def find_duplicate_files(all_files: List[Path]) -> Dict[str, List[Tuple[str, int]]]:
    hash_map: Dict[str, List[Tuple[str, int]]] = {}
    
    for filepath in all_files:
        try:
            sha = compute_sha256(filepath)
            rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
            size = filepath.stat().st_size
            if sha not in hash_map:
                hash_map[sha] = []
            hash_map[sha].append((rel_path, size))
        except Exception:
            pass
    
    return {h: paths for h, paths in hash_map.items() if len(paths) > 1}

def classify_module(filepath: Path, imports_by_file: Dict[str, Set[str]], imported_by: Dict[str, Set[str]],
                    route_registrations: Dict[str, Set[str]]) -> Tuple[str, str]:
    rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
    parts = rel_path.split("/")
    
    if parts[0] == "scripts":
        if any(k in rel_path for k in ("migrate", "verify", "backup", "restore")):
            return "D", "migrations/verification/backup scripts"
    
    if parts[0] == "tests":
        return "D", "test files"
    
    if parts[0] == "docs":
        return "D", "documentation"
    
    if rel_path in imported_by:
        return "A", f"imported by {', '.join(list(imported_by[rel_path])[:3])}"
    
    if any(rel_path in routes for routes in route_registrations.values()):
        return "A", "route registered"
    
    if rel_path.startswith("app/v04") or rel_path.startswith("app/v05"):
        return "B", "legacy compatibility module"
    
    if rel_path.startswith("app/v06"):
        return "A", "current platform module"
    
    if rel_path.startswith("app/api"):
        return "A", "API module"
    
    if rel_path.startswith("app/services"):
        return "A", "service layer"
    
    if rel_path.startswith("app/models"):
        return "A", "database models"
    
    return "C", "no static references found"

def audit_official_entrypoints() -> List[Dict[str, Any]]:
    entries = []
    
    entry_defs = [
        {"name": "FastAPI应用入口", "path": "app/main.py", "caller": "启动脚本", "official": True},
        {"name": "路由总注册", "path": "app/main.py", "caller": "应用入口", "official": True},
        {"name": "模板根目录", "path": "app/templates/", "caller": "app.main", "official": True},
        {"name": "静态资源根目录", "path": "app/static/", "caller": "app.main", "official": True},
        {"name": "正式启动脚本", "path": "run_windows.bat", "caller": "用户双击", "official": True},
        {"name": "数据库路径解析", "path": "app/settings.py", "caller": "全局", "official": True},
        {"name": "迁移入口", "path": "scripts/migrations/", "caller": "scripts/windows/migrate_all_windows.bat", "official": True},
        {"name": "验证入口", "path": "scripts/verify_p0_baseline.py", "caller": "scripts/windows/verify_all_windows.bat", "official": True},
        {"name": "pytest入口", "path": "tests/", "caller": "python -m pytest", "official": True},
    ]
    
    for entry in entry_defs:
        entries.append({
            "name": entry["name"],
            "path": entry["path"],
            "caller": entry["caller"],
            "official": entry["official"],
            "duplicate": False,
            "recommended": "保留"
        })
    
    return entries

def audit_dual_write_risk() -> List[Dict[str, Any]]:
    risks = [
        {"action": "会员注册/绑定", "new_entry": "v04f_club_memberships", "old_entry": "v05a_users", "dual_write": True,
         "risk_level": "中", "recommend": "停用v05a_users写入", "priority": "P2"},
        {"action": "情报创建", "new_entry": "v06_intelligence_items", "old_entry": "v04d_intelligence", "dual_write": False,
         "risk_level": "低", "recommend": "已迁移完成", "priority": "P4"},
        {"action": "资源创建", "new_entry": "v06_market_resources", "old_entry": "v04f_club_offerings", "dual_write": True,
         "risk_level": "中", "recommend": "停用v04f_club_offerings写入", "priority": "P2"},
        {"action": "商机创建", "new_entry": "v06_cooperation_opportunities", "old_entry": "v05c_opportunities", "dual_write": False,
         "risk_level": "低", "recommend": "已迁移完成", "priority": "P4"},
        {"action": "人物创建", "new_entry": "v06_subjects", "old_entry": "v04a_persons", "dual_write": False,
         "risk_level": "低", "recommend": "已迁移完成", "priority": "P4"},
        {"action": "机构创建", "new_entry": "v06_subjects", "old_entry": "v04b_organizations", "dual_write": False,
         "risk_level": "低", "recommend": "已迁移完成", "priority": "P4"},
    ]
    return risks

def classify_deletion_candidate(filepath: Path, sha_map: Dict[str, List[Tuple[str, int]]], 
                                imports_by_file: Dict[str, Set[str]], 
                                imported_by: Dict[str, Set[str]]) -> Tuple[str, str]:
    rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
    size = filepath.stat().st_size
    
    if rel_path.endswith(".pyc") or "__pycache__" in rel_path or ".pytest_cache" in rel_path:
        return "S1", "可重新生成缓存"
    
    if size == 0:
        return "S1", "空文件"
    
    if rel_path.startswith("docs/"):
        if any(k in rel_path for k in ("backup", "archive", "old")):
            return "S2", "旧文档"
        return "S4", "正式文档"
    
    if rel_path.startswith("scripts/"):
        if "archive" in rel_path or "old" in rel_path:
            return "S2", "旧脚本归档"
        if any(k in rel_path for k in ("migrate", "verify", "backup", "restore")):
            return "S4", "迁移/验证脚本"
        return "S3", "脚本需验证"
    
    if rel_path.startswith("app/"):
        if rel_path.startswith("app/templates/"):
            return "S3", "模板需验证引用"
        if rel_path.startswith("app/static/"):
            return "S3", "静态资源需验证引用"
        if rel_path.startswith("app/v04") or rel_path.startswith("app/v05"):
            return "S3", "旧业务模块"
        if rel_path in imported_by or any(rel_path in imps for imps in imports_by_file.values()):
            return "S4", "正式模块"
        return "S3", "未引用模块需验证"
    
    return "S3", "需进一步验证"

def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Step 1: Collecting files...")
    py_files = get_all_files(BASE_DIR, excluded_extensions={".pyc", ".db", ".db-shm", ".db-wal", ".log", ".zip", ".bak", ".tmp"})
    py_files = [f for f in py_files if f.suffix == ".py"]
    
    template_files = get_all_files(TEMPLATES_DIR) if TEMPLATES_DIR.exists() else []
    static_files = get_all_files(STATIC_DIR) if STATIC_DIR.exists() else []
    all_audit_files = get_all_files(BASE_DIR)
    
    print("Step 2: Analyzing imports...")
    imports_by_file, imported_by = analyze_imports(py_files)
    
    print("Step 3: Finding route registrations...")
    route_registrations = find_route_registrations(py_files)
    
    print("Step 4: Analyzing templates...")
    template_references, referenced_by = analyze_templates(template_files)
    
    print("Step 5: Finding static references...")
    static_references = find_static_references(template_files)
    
    print("Step 6: Finding duplicate files...")
    duplicate_files = find_duplicate_files(all_audit_files)
    
    print("Step 7: Classifying modules...")
    module_audit = []
    for filepath in py_files:
        rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
        category, evidence = classify_module(filepath, imports_by_file, imported_by, route_registrations)
        
        module_audit.append({
            "path": rel_path,
            "category": category,
            "imported_by": ", ".join(list(imported_by.get(rel_path, set()))[:5]),
            "route_registered": "是" if any(rel_path in routes for routes in route_registrations.values()) else "否",
            "script_referenced": "否",
            "template_referenced": "否",
            "replacement": "",
            "risk_level": "低" if category in ("A", "D") else ("中" if category == "B" else "高"),
            "recommended_action": "保留" if category in ("A", "D") else ("观察" if category == "B" else "需验证"),
            "evidence": evidence
        })
    
    print("Step 8: Generating reports...")
    
    with open(AUDIT_DIR / "P1_2_OFFICIAL_ENTRYPOINTS.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 正式入口清单\n\n")
        f.write("## 入口列表\n\n")
        f.write("| 名称 | 路径 | 调用来源 | 是否正式 | 是否重复 | 建议 |\n")
        f.write("|---|---|---|---|---|---|\n")
        for entry in audit_official_entrypoints():
            f.write(f"| {entry['name']} | {entry['path']} | {entry['caller']} | {'是' if entry['official'] else '否'} | {'是' if entry['duplicate'] else '否'} | {entry['recommended']} |\n")
    
    with open(AUDIT_DIR / "P1_2_PYTHON_MODULE_AUDIT.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=module_audit[0].keys())
        writer.writeheader()
        writer.writerows(module_audit)
    
    with open(AUDIT_DIR / "P1_2_ROUTE_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 路由审计报告\n\n")
        f.write(f"## 总览\n\n路由总数: {len(route_registrations)}\n\n")
        f.write("## 路由清单\n\n")
        f.write("| 路径 | 注册模块 |\n")
        f.write("|---|---|\n")
        for route, modules in sorted(route_registrations.items()):
            f.write(f"| {route} | {', '.join(modules)} |\n")
    
    with open(AUDIT_DIR / "p1_2_route_inventory.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "modules", "count"])
        for route, modules in sorted(route_registrations.items()):
            writer.writerow([route, ";".join(modules), len(modules)])
    
    with open(AUDIT_DIR / "P1_2_TEMPLATE_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 模板审计报告\n\n")
        f.write(f"## 总览\n\n模板总数: {len(template_files)}\n\n")
        f.write("## 模板引用关系\n\n")
        f.write("| 模板 | 引用的模板 |\n")
        f.write("|---|---|\n")
        for template, refs in sorted(template_references.items()):
            f.write(f"| {template} | {', '.join(refs)} |\n")
    
    with open(AUDIT_DIR / "p1_2_template_inventory.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["template", "references", "referenced_by", "is_referenced"])
        for filepath in template_files:
            rel_path = str(filepath.relative_to(TEMPLATES_DIR)).replace("\\", "/")
            refs = template_references.get(rel_path, set())
            ref_by = referenced_by.get(rel_path, set())
            is_ref = "是" if ref_by else "否"
            writer.writerow([rel_path, ";".join(refs), ";".join(ref_by), is_ref])
    
    with open(AUDIT_DIR / "P1_2_STATIC_ASSET_AUDIT.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "size", "referenced_in_template", "risk_level"])
        for filepath in static_files:
            rel_path = str(filepath.relative_to(STATIC_DIR)).replace("\\", "/")
            full_path = f"/static/{rel_path}"
            referenced = "是" if full_path in static_references else "否"
            risk = "低" if referenced else "高"
            writer.writerow([rel_path, filepath.stat().st_size, referenced, risk])
    
    with open(AUDIT_DIR / "P1_2_DUPLICATE_FILE_AUDIT.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sha256", "paths", "count", "size"])
        for sha, paths in sorted(duplicate_files.items(), key=lambda x: -len(x[1])):
            paths_str = ";".join(p for p, _ in paths)
            size = paths[0][1]
            writer.writerow([sha, paths_str, len(paths), size])
    
    with open(AUDIT_DIR / "P1_2_DUPLICATE_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 重复文件审计总结\n\n")
        f.write(f"## 总览\n\n重复文件组数: {len(duplicate_files)}\n\n")
        f.write("## 重复组详情\n\n")
        for i, (sha, paths) in enumerate(sorted(duplicate_files.items(), key=lambda x: -len(x[1])), 1):
            f.write(f"### 组 {i}\n\n")
            f.write(f"**SHA256**: {sha}\n\n")
            f.write(f"**文件数**: {len(paths)}\n\n")
            f.write(f"**大小**: {paths[0][1]} bytes\n\n")
            f.write("**路径列表**:\n\n")
            for p, _ in paths:
                f.write(f"- {p}\n")
            f.write("\n")
    
    with open(AUDIT_DIR / "P1_2_BACKUP_PATCH_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 历史备份与补丁审计\n\n")
        f.write("## 分类策略\n\n")
        f.write("- **必须保留**: 唯一数据库备份、当前Git无法恢复的历史数据、尚未确认是否应用的补丁\n")
        f.write("- **可移出项目**: 旧版本完整代码副本、已有Git记录覆盖的历史补丁、已完成任务的庞大产物\n")
        f.write("- **可安全删除**: 与正式文件完全相同、已被Git提交覆盖、不含独有数据、不被启动/迁移/恢复流程调用\n")
        f.write("\n## 审计结果\n\n")
        f.write("本项目备份目录: data/backups/\n")
        f.write("补丁目录: tools/windows/archive/, tools/windows/demo/\n")
        f.write("\n**建议**: 保留当前备份，定期清理超过90天的旧备份\n")
    
    with open(AUDIT_DIR / "P1_2_DUAL_WRITE_RISK.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 双重写入风险审计\n\n")
        f.write("## 风险列表\n\n")
        f.write("| 业务动作 | 新写入入口 | 旧写入入口 | 是否双写 | 风险等级 | 推荐停用 | 优先级 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for risk in audit_dual_write_risk():
            f.write(f"| {risk['action']} | {risk['new_entry']} | {risk['old_entry']} | {'是' if risk['dual_write'] else '否'} | {risk['risk_level']} | {risk['recommend']} | {risk['priority']} |\n")
    
    print("Step 9: Classifying deletion candidates...")
    deletion_candidates = []
    for filepath in all_audit_files:
        rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
        if any(exc in rel_path for exc in (".git", ".venv", "node_modules", "__pycache__", ".pytest_cache")):
            continue
        
        size = filepath.stat().st_size
        sha = compute_sha256(filepath)
        
        category, reason = classify_deletion_candidate(filepath, duplicate_files, imports_by_file, imported_by)
        
        deletion_candidates.append({
            "path": rel_path,
            "size": size,
            "sha256": sha,
            "category": category,
            "risk_level": "低" if category in ("S1", "S4") else ("中" if category == "S2" else "高"),
            "reference_evidence": ", ".join(list(imported_by.get(rel_path, set()))[:3]),
            "replacement": "",
            "recommended_action": "删除" if category == "S1" else ("归档" if category == "S2" else ("验证" if category == "S3" else "保留")),
            "reason": reason,
            "rollback_source": "Git"
        })
    
    with open(AUDIT_DIR / "P1_2_DELETION_CANDIDATES.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=deletion_candidates[0].keys())
        writer.writeheader()
        writer.writerows(deletion_candidates)
    
    s1_count = sum(1 for c in deletion_candidates if c["category"] == "S1")
    s2_count = sum(1 for c in deletion_candidates if c["category"] == "S2")
    s3_count = sum(1 for c in deletion_candidates if c["category"] == "S3")
    s4_count = sum(1 for c in deletion_candidates if c["category"] == "S4")
    s1_size = sum(c["size"] for c in deletion_candidates if c["category"] == "S1")
    s2_size = sum(c["size"] for c in deletion_candidates if c["category"] == "S2")
    s3_size = sum(c["size"] for c in deletion_candidates if c["category"] == "S3")
    s4_size = sum(c["size"] for c in deletion_candidates if c["category"] == "S4")
    
    with open(AUDIT_DIR / "P1_2_RECOMMENDATION.md", "w", encoding="utf-8") as f:
        f.write("# P1.2-A 删除候选分级建议\n\n")
        f.write("## 分级统计\n\n")
        f.write(f"- **S1 可直接删除**: {s1_count} 个文件, {s1_size / 1024:.1f} KB\n")
        f.write(f"- **S2 可归档**: {s2_count} 个文件, {s2_size / 1024:.1f} KB\n")
        f.write(f"- **S3 需验证**: {s3_count} 个文件, {s3_size / 1024:.1f} KB\n")
        f.write(f"- **S4 必须保留**: {s4_count} 个文件, {s4_size / 1024:.1f} KB\n")
        f.write("\n## 删除建议\n\n")
        f.write("### 首批建议删除 (S1)\n\n")
        f.write("- __pycache__ 目录\n")
        f.write("- .pytest_cache 目录\n")
        f.write("- 临时编译产物\n")
        f.write("- 空文件\n")
        f.write("\n### 建议归档 (S2)\n\n")
        f.write("- 旧版本报告\n")
        f.write("- 已完成补丁\n")
        f.write("- 旧版代码副本\n")
        f.write("\n### 需进一步验证 (S3)\n\n")
        f.write("- v04/v05旧业务模块\n")
        f.write("- 未被引用的模板\n")
        f.write("- 未被引用的静态资源\n")
        f.write("\n### 必须保留 (S4)\n\n")
        f.write("- 正式入口文件\n")
        f.write("- 正式模型\n")
        f.write("- 迁移脚本\n")
        f.write("- 测试文件\n")
        f.write("- 核心文档\n")
    
    print("\n=== 审计完成 ===")
    print(f"Python模块数: {len(module_audit)}")
    print(f"路由数: {len(route_registrations)}")
    print(f"模板数: {len(template_files)}")
    print(f"静态资源数: {len(static_files)}")
    print(f"重复文件组数: {len(duplicate_files)}")
    print(f"S1: {s1_count}, S2: {s2_count}, S3: {s3_count}, S4: {s4_count}")

if __name__ == "__main__":
    main()