# 已知问题

| 编号 | 位置 | 表现 | 严重级别 | 状态 | 验证方式 | 阻塞发布 |
|---|---|---|---|---|---|---|
| KI-001 | 根目录备份、补丁和 `data/backups` | 897 组完全重复文件，潜在重复约 147 MB | 中 | 保留待人工确认 | `docs/REDUNDANCY_REVIEW.md` | 否 |
| KI-002 | 历史 `v04*`/`v05*` 模块 | 命名过时但仍被路由、迁移和验证引用 | 中 | deprecated/兼容 | `python -m compileall app scripts`、核心冒烟 | 否 |
| KI-003 | 审计与性能记录 | API 冒烟直接针对正式库会改变数据库哈希 | 高 | 验证改用临时副本 | `scripts/verify_p0_baseline.py` | 是，若验证仍直连正式库 |
| KI-004 | 领域迁移 | 旧表到正式模型存在待人工确认的冲突与空外键 | 中 | P1 迁移仅 dry-run/副本验证 | `scripts/verify_domain_consolidation_v1.py` | 否 |

| KI-005 | `v06_timeline_entries` | 12 条历史记录引用不存在的机会（ID 1、12、13） | 高 | 待人工核对，不自动修复 | `PRAGMA foreign_key_check` | 否，迁移未增加 |
| KI-006 | 俱乐部板块 | 某页面进入统一错误页（500） | 中 | 待定位根因 | 人工验收 | 否 |
| KI-007 | 俱乐部运营与活动指标 | 数据键仍使用 `successful_matches`、`recent_events`、`event_registrations`、`today_checkins`、`post_event_followups`；不属于 P2.1 情报链 | 低 | 待俱乐部模块本地化任务处理 | 检查俱乐部运营页面指标标签 | 否 |
