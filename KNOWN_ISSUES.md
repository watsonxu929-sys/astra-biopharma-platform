# 已知问题

| 编号 | 位置 | 表现 | 严重级别 | 状态 | 验证方式 | 阻塞发布 |
|---|---|---|---|---|---|---|
| KI-008 | P2.2 XLSX规则处理 | 单份历史审批表产生513个候选，人工审核负担过高 | 高 | 待增加工作表/列语义与每文档上限 | 副本批次 `P22-20260711-CODEX` | 是，阻塞扩大试点 |
| KI-009 | P2.2 AI评测 | 本机无OpenAI Key/SDK，AI与Hybrid指标未运行 | 中 | `not_run`，不得用Rule冒充 | `evaluation/p2_2/evaluation_results.json` | 是，阻塞AI效果结论 |
| KI-010 | 正式库文件保护 | 开始SHA为 `3C2982...E8E`，最终为 `D33416...480`；试点均指向副本，主文件最后写入早于试点，可能与SQLite WAL检查点有关，但无开始时一致性副本可证明 | 高 | 待人工核查，禁止宣称SHA保护通过 | 文件时间、WAL与副本审计 | 是，阻塞完全验收 |

| 编号 | 位置 | 表现 | 严重级别 | 状态 | 验证方式 | 阻塞发布 |
|---|---|---|---|---|---|---|
| KI-001 | 根目录备份、补丁和 `data/backups` | 897 组完全重复文件，潜在重复约 147 MB | 中 | 保留待人工确认 | `docs/REDUNDANCY_REVIEW.md` | 否 |
| KI-002 | 历史 `v04*`/`v05*` 模块 | 命名过时但仍被路由、迁移和验证引用 | 中 | deprecated/兼容 | `python -m compileall app scripts`、核心冒烟 | 否 |
| KI-003 | 审计与性能记录 | API 冒烟直接针对正式库会改变数据库哈希 | 高 | 验证改用临时副本 | `scripts/verify_p0_baseline.py` | 是，若验证仍直连正式库 |
| KI-004 | 领域迁移 | 旧表到正式模型存在待人工确认的冲突与空外键 | 中 | P1 迁移仅 dry-run/副本验证 | `scripts/verify_domain_consolidation_v1.py` | 否 |

| KI-005 | `v06_timeline_entries` | 12 条历史记录引用不存在的机会（ID 1、12、13） | 高 | 待人工核对，不自动修复 | `PRAGMA foreign_key_check` | 否，迁移未增加 |
| KI-006 | 俱乐部板块 | 某页面进入统一错误页（500） | 中 | 待定位根因 | 人工验收 | 否 |
| KI-007 | 俱乐部运营与活动指标 | 数据键仍使用 `successful_matches`、`recent_events`、`event_registrations`、`today_checkins`、`post_event_followups`；不属于 P2.1 情报链 | 低 | 待俱乐部模块本地化任务处理 | 检查俱乐部运营页面指标标签 | 否 |


## P2.3 已知问题

- 事件融合为确定性规则首版，复杂别名、同义产品名和跨语言文本仍需人工确认。
- 试点三家企业仅在数据库副本中以 P2.3 pilot 来源创建，尚未进入正式主体匹配。
- 82 个模板中 9 个既有 platform/* 模板因缺少 status_label 过滤器未通过独立模板检查；P2.3 模板通过，本任务不扩修全站 UI。
- 正式库起止文件 SHA256 不一致；正式库没有 p2_3_* 表或新增研究数据。现有连接助手设置 WAL，需人工确认物理文件头变化，详见 docs/p2/P2_3_ERROR_ANALYSIS.md。
