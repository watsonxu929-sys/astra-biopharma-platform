# 项目资产盘点

盘点时间：2026-07-10。业务代码未在盘点阶段修改。

## 数量与入口

- Python：276；Jinja2/HTML 模板：79；JavaScript：1；CSS：6。
- 迁移脚本：28；验证脚本：49；带版本号应用模块：19。
- 应用入口：`app/main.py:app`；路由注册在 `app/main.py`，API 聚合入口为 `app/api/v1/router.py`。
- 启动入口：`run_windows.bat`、`start_web_windows.bat`、`start_all_windows.bat`。
- 迁移入口：`migrate_all_windows.bat` → `scripts/migrate_all.py`，以及版本化 `scripts/migrate_*.py`。
- 验证入口：`verify_all_windows.bat` → `scripts/verify_all.py`，P0 入口为 `scripts/verify_p0_baseline.py`。

## 数据库

- 正式开发库：`data/app.db`，初始大小 2,494,464 字节；初始 SHA256 `2DD7F3EE6D8EF6C658A29316C8667030777A285892AAEE9D2272F2BE8E7284D7`。
- `data/backups/` 含大量历史 SQLite 备份；不删除、不提交 Git。
- P0 外部完整备份：`../biopharma-intelligence-pre-p0-p1-20260710-100816.zip`，73,458,330 字节，SHA256 `3D1F6C2930ECA999F196AD4A0CF73F178D5A8DBA529B643B3AB61BA2FA8EB80B`。

## 版本模块

`app/v04c1_ingestion.py`、`v04c_review.py`、`v04d_structuring.py`、`v04db_prestructure.py`、`v04e_entity_resolution.py`、`v04f_operations.py`、`v04g_monitoring.py`、`v04h_recommendations.py`、`v05a_security.py`、`v05b_member_import.py`、`v05c_club_events.py`、`v05d_member_portal.py`、`v05e_intelligence.py`、`v05f_collection.py`、`v05g_processing.py`、`v05h_reports.py`、`v05i_pipeline.py`、`v05j_research.py`、`v05kl_operations.py` 均由 `app/main.py` 注册或被服务/迁移引用，本次不删除。

## 重复、备份与候选

- 对排除 `.git` 和 `.venv` 的 3,737 个文件计算 SHA256：897 个重复组、3,085 个重复文件，理论重复字节 147,370,347。
- 高重复来源：`backups/`、`backup_before_v05m_recovery_20260702_091828/`、`patches/`、`data/backups/`。
- 这些目录含唯一历史代码或真实数据的可能性，全部保留并登记到 `docs/REDUNDANCY_REVIEW.md`。
- 只自动清理 `__pycache__`、`.pyc` 和测试/工具缓存；清单见 `docs/DELETION_MANIFEST.md`。

## 运行时迁移审计

应用层存在 `ensure_schema()`、`executescript()` 和迁移函数调用。P0 后所有相关入口默认 `allow_migration=False`；只有显式迁移和隔离验证可传 `allow_migration=True`。普通页面/服务调用不再执行 DDL。
