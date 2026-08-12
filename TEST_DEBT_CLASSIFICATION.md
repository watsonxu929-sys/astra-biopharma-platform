# TEST DEBT CLASSIFICATION

执行日期：2026-08-10（Asia/Shanghai）
命令：`.venv\Scripts\python.exe -m pytest -ra --tb=short --junitxml=data\acceptance\mvp_rc1_full_pytest_20260810.xml`
数据库：RC1 内隔离副本；正式 `data/app.db` 前后 SHA256 未变化。

## 总览

| 结果 | 数量 |
|---|---:|
| Passed | 66 |
| Failed | 12 |
| Error | 34 |
| Skipped | 1 |
| Warning | 7 |

46 个 failed/error 的分类为：A=0、B=0、C=0、D=34、E=12、F=0。另有 2 个 Windows 子进程 UTF-8 解码 warning 属于 C，但不是 failed/error。

本轮在 pytest 之前发现并修复了 2 个真实 A 类 P1 工程缺陷：全新环境缺少 `apscheduler` 依赖声明、`scripts/runtime_info.py Worker` 无法从标准入口运行。修复后 Web、Worker 状态、六导航和 Golden Loop 均通过；因此以下 pytest 债务中没有剩余 A 类 P0/P1。

## D：历史 migration / 旧数据库假设（34 项）

### `tests/test_p3_entity_relationship_network.py`（21 ERROR）

共同错误摘要：fixture 把旧 `scripts/migrations/006_entity_relationship_network.py --apply` 重新施加到当前 Canonical 数据库副本，旧脚本以 relationship type 总数必须等于旧常量作为成功条件，遇到 RC1 已扩展/演进的 schema 后统一 `schema_verification_failed`。模块为产业关系历史迁移测试；实测 `/network` 与 Golden Loop 正常，因此不影响六导航或 Golden Loop。建议均为：**更新** fixture，直接复制当前 Canonical schema；旧 006 幂等场景单独**冻结**为历史迁移验收，不恢复旧 schema。

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_migration_is_idempotent` | `tests/test_p3_entity_relationship_network.py` | 旧 006 在当前副本上验证失败 | P3 migration | D | 否 | 否 | 冻结旧 006；新增当前链验收 |
| `test_product_asset_is_separate_from_project` | 同上 | fixture 旧 006 setup 失败 | P3 主体模型 | D | 否 | 否 | 更新 fixture |
| `test_alias_and_public_identifier` | 同上 | fixture 旧 006 setup 失败 | P3 主体解析 | D | 否 | 否 | 更新 fixture |
| `test_same_name_person_is_weak_without_context` | 同上 | fixture 旧 006 setup 失败 | P3 主体解析 | D | 否 | 否 | 更新 fixture |
| `test_exact_public_identifier_is_strong` | 同上 | fixture 旧 006 setup 失败 | P3 主体解析 | D | 否 | 否 | 更新 fixture |
| `test_alias_match_is_medium` | 同上 | fixture 旧 006 setup 失败 | P3 主体解析 | D | 否 | 否 | 更新 fixture |
| `test_resolution_review_requires_permission` | 同上 | fixture 旧 006 setup 失败 | P3 权限 | D | 否 | 否 | 更新 fixture |
| `test_relationship_type_registry_covers_five_groups` | 同上 | fixture 旧 006 setup 失败 | P3 关系类型 | D | 否 | 否 | 更新 Canonical 断言 |
| `test_relationship_endpoint_type_is_validated` | 同上 | fixture 旧 006 setup 失败 | P3 关系校验 | D | 否 | 否 | 更新 fixture |
| `test_high_risk_relationship_needs_evidence` | 同上 | fixture 旧 006 setup 失败 | P3 关系证据 | D | 否 | 否 | 更新 fixture |
| `test_evidence_is_structured_and_retained_on_archive` | 同上 | fixture 旧 006 setup 失败 | P3 关系证据 | D | 否 | 否 | 更新 fixture |
| `test_manual_unverified_relationship_can_be_low_risk` | 同上 | fixture 旧 006 setup 失败 | P3 风险规则 | D | 否 | 否 | 更新 fixture |
| `test_temporal_overlap_creates_conflict_candidate` | 同上 | fixture 旧 006 setup 失败 | P3 时态关系 | D | 否 | 否 | 更新 fixture |
| `test_history_filter` | 同上 | fixture 旧 006 setup 失败 | P3 时态关系 | D | 否 | 否 | 更新 fixture |
| `test_merge_preview_does_not_mutate_source` | 同上 | fixture 旧 006 setup 失败 | P3 合并治理 | D | 否 | 否 | 更新 fixture |
| `test_merge_execute_redirect_and_rollback` | 同上 | fixture 旧 006 setup 失败 | P3 合并治理 | D | 否 | 否 | 更新 fixture |
| `test_path_engine_returns_two_hops` | 同上 | fixture 旧 006 setup 失败 | P3 路径引擎 | D | 否 | 否 | 更新 fixture |
| `test_path_engine_caps_depth_at_three` | 同上 | fixture 旧 006 setup 失败 | P3 路径引擎 | D | 否 | 否 | 更新 fixture |
| `test_connection_candidates_require_evidence` | 同上 | fixture 旧 006 setup 失败 | P3 连接候选 | D | 否 | 否 | 更新 fixture |
| `test_connection_candidate_is_explainable_and_not_an_action` | 同上 | fixture 旧 006 setup 失败 | P3 连接候选 | D | 否 | 否 | 更新 fixture |
| `test_web_entry_and_empty_queues_are_discoverable` | 同上 | fixture 旧 006 setup 失败 | P3 Web 入口 | D | 否（实测 200） | 否 | 更新 fixture 后保留行为断言 |

### `tests/test_p3_network_invariants.py`（8 ERROR）

共同错误、影响与建议同上：全部在测试体执行前被旧 006 fixture 阻断。

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_unapproved_candidate_is_not_in_network` | `tests/test_p3_network_invariants.py` | 旧 006 setup 失败 | P3 不变量 | D | 否 | 否 | 更新 fixture |
| `test_merge_cannot_execute_before_approval` | 同上 | 旧 006 setup 失败 | P3 审批 | D | 否 | 否 | 更新 fixture |
| `test_invalid_period_is_rejected` | 同上 | 旧 006 setup 失败 | P3 时态校验 | D | 否 | 否 | 更新 fixture |
| `test_multiple_sources_are_counted_and_linked` | 同上 | 旧 006 setup 失败 | P3 证据 | D | 否 | 否 | 更新 fixture |
| `test_one_hop_and_no_path_results` | 同上 | 旧 006 setup 失败 | P3 路径引擎 | D | 否 | 否 | 更新 fixture |
| `test_cycles_do_not_repeat_nodes` | 同上 | 旧 006 setup 失败 | P3 路径引擎 | D | 否 | 否 | 更新 fixture |
| `test_restricted_relationship_is_filtered_by_default` | 同上 | 旧 006 setup 失败 | P3 隐私 | D | 否 | 否 | 更新 fixture |
| `test_directly_connected_person_is_not_recommended` | 同上 | 旧 006 setup 失败 | P3 连接候选 | D | 否 | 否 | 更新 fixture |

### `tests/test_p4_club_operations_mvp.py`（1 FAIL + 2 ERROR）

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_007_is_idempotent_and_keeps_integrity` | `tests/test_p4_club_operations_mvp.py` | fixture 先执行旧 006，setup 失败 | P4/Q-BAY migration | D | 否（Q-BAY 实测 200） | 否 | 更新迁移基线 |
| `test_controlled_pilot_closes_the_workflow_without_formal_mutation` | 同上 | pilot 在正式库副本上重放旧 006，`schema_verification_failed` | P4 pilot | D | 否 | 否 | 更新 pilot 链；不得恢复旧 schema |
| `test_unauthenticated_user_cannot_run_club_review` | 同上 | fixture 先执行旧 006，setup 失败 | P4 权限 | D | 否 | 否 | 更新 fixture 后保留权限断言 |

### `tests/test_v06j_migration_chain.py`（2 FAIL）

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_empty_database_upgrades_to_008_without_business_seed_and_is_idempotent` | `tests/test_v06j_migration_chain.py` | 旧 000–008 空库链假设缺少 `lifecycle_status` | v06j migration | D | 否 | 否 | 冻结旧链，建立 RC1 新库基线测试 |
| `test_formal_database_copy_upgrades_without_changing_old_rows` | 同上 | 当前正式库副本被旧链判定 `schema_drift_detected` | v06j migration | D | 否 | 否 | 更新 Canonical drift 清单；禁止对正式库重放旧链 |

## E：测试与当前 Canonical 规则冲突（12 项）

### `tests/test_v06i_runtime_baseline.py`（9 FAIL）

共同原因：测试期待一套合并后的 `app.settings.Settings`、SchemaPreflight、动态导航隐藏及纯内存 auth bypass 契约；当前 RC1 的正式运行路径分别使用 `app.settings` 与 `app.core.config`，正式库 schema 完整，浏览器和脱敏状态命令均已实测通过。建议先确定 Canonical 配置契约，再**更新测试**，不得为测试数字大规模恢复未落地的 v06i 行为。

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_database_url_priority` | `tests/test_v06i_runtime_baseline.py` | 测试期待 `Settings.sqlite_path`，当前对象字段为 `app_db_path` | runtime config | E | 否 | 否 | 更新到 Canonical 字段/解析函数 |
| `test_production_safety_rejects_missing_secrets_and_bypasses` | 同上 | 测试构造当前 `Settings` 不接受的 `auth_disabled` 字段 | runtime safety | E | 否（本地 RC1） | 否 | 统一配置模型后更新测试 |
| `test_preflight_is_read_only_and_reports_extension_gaps` | 同上 | 测试省略当前必需 `app_db_path` | schema preflight | E | 否 | 否 | 更新测试构造器 |
| `test_preflight_complete_schema_and_missing_file` | 同上 | 测试省略当前必需 `app_db_path` | schema preflight | E | 否 | 否 | 更新测试构造器 |
| `test_preflight_reports_unavailable_database` | 同上 | 测试省略当前必需 `app_db_path` | schema preflight | E | 否 | 否 | 更新测试构造器 |
| `test_capability_guard_returns_page_and_structured_api_503` | 同上 | SchemaPreflight 期待 `db_backend`，拿到另一 Settings 类型 | capability guard | E | 否（正式 schema 完整） | 否 | 统一配置类型后更新测试 |
| `test_navigation_hides_unavailable_schema_capabilities` | 同上 | 测试期待 schema 动态隐藏，当前 registry 只按权限过滤 | navigation | E | 否（实测六导航正常） | 否 | 明确 Canonical 规则后更新/冻结 |
| `test_auth_bypass_is_explicit_in_memory_only` | 同上 | 测试直接调用旧 helper 并期待无库纯内存用户；当前正式中间件走内存主体但 helper 契约不同 | auth bypass | E | 否 | 否 | 更新为中间件 Canonical 测试 |
| `test_missing_auth_schema_is_controlled_and_read_only` | 同上 | 测试期待空库 503；当前安全层尝试读取 `v05a_users` | missing-schema fallback | E | 否（正式库表存在） | 否 | 作为后续健壮性任务更新，不在本轮扩修 |

### `tests/test_v06k_p4_operations_contract.py`（3 ERROR）

共同错误摘要：fixture 依赖历史 `data/rehearsal/v06j_app_migrated.db`，并期待 `ClubOperationsDashboardService.summary()["web_metrics"]`；当前 Canonical 服务返回 `metrics`，Q-BAY 页面使用当前契约且浏览器实测正常。

| 测试名称 | 文件 | 错误摘要 | 模块 | 分类 | 影响六导航 | 影响 Golden Loop | 建议 |
|---|---|---|---|---|---|---|---|
| `test_p4_field_contract_uses_joined_events_date` | `tests/test_v06k_p4_operations_contract.py` | fixture `KeyError: web_metrics` | Q-BAY contract | E | 否（Q-BAY 实测 200） | 否 | 更新为当前 `metrics` 契约与 RC1 副本 |
| `test_p4_permissions_and_missing_schema_are_controlled` | 同上 | fixture `KeyError: web_metrics` | Q-BAY 权限 | E | 否 | 否 | 更新 fixture 后保留权限断言 |
| `test_p4_closed_loop_persists_after_refresh_and_client_restart` | 同上 | fixture `KeyError: web_metrics` | Q-BAY 闭环 | E | 否 | 否 | 更新 fixture；不要恢复旧返回键 |

## C 类 warning（非失败项）

`tests/test_p4_club_operations_mvp.py` 的两个用例触发 `subprocess` reader thread `UnicodeDecodeError`，因为 Windows 子进程输出并非 UTF-8，却以 `text=True/encoding=utf-8` 读取。建议后续单独更新子进程编码处理；它没有改变本轮 12 failed / 34 error 计数。

## 本轮处置原则

- 不为了清零 pytest 恢复旧 006/007、v06i、v06j 或 v06k 行为。
- D/E/C 类只记录；下一任务应先统一当前 Canonical 测试 fixture 和配置契约，再逐组更新。
- 真实 RC1 验收权重高于历史测试：六个主导航浏览器通过，Golden Loop 独立副本完整通过，正式数据库未变化。
