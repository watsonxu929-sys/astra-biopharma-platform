# MVP-R3 Migration Baseline

基线时间：2026-08-24（Asia/Shanghai）

| 项目 | 实时结果 |
|---|---|
| Project absolute path | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| Branch | `release/mvp-rc1.2` |
| HEAD | `ce470ad95b86e69a1e7eb03293bbfa7f9a12348a` |
| Entry git status | clean（Skill preflight `changed_count=0`） |
| DB absolute path | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| DB SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` |
| SQLite integrity_check | `ok` |
| 非 SQLite 内部表总数 | `187` |

## 实时业务行数

| Table | Rows |
|---|---:|
| people | 44 |
| organizations | 24 |
| projects | 5 |
| relations | 26 |
| p3_canonical_relationships | 0 |
| p3_relationship_evidence | 0 |
| resources | 8 |
| v04f_club_needs | 0 |
| v04f_club_offerings | 1 |
| v06_market_resources | 20 |
| v04f_club_matches | 0 |
| p4_resource_match_candidates | 0 |
| v04f_lead_records | 0 |
| v04f_lead_stage_history | 0 |
| v04f_lead_suggestions | 0 |
| p4_club_lead_candidates | 0 |
| actions | 7 |
| v06_opportunities | 11 |
| v06_follow_ups | 4 |
| v06_collab_tasks | 4 |

以上全部来自本轮 SQLite `mode=ro` 实时查询，不引用旧报告数字。
