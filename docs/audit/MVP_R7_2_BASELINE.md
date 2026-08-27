# MVP-R7.2 Baseline

记录日期：2026-08-28（Asia/Shanghai）

## Git

- 唯一正式项目：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`
- Branch：`release/mvp-rc1.2`
- HEAD：`a07e93b3d5fcd6db69233a5d2686949e26e6feb6`
- Commit：`MVP-R7.1 admin operability and source discovery`
- Working Tree：`clean`

## Database

- DB path：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`
- SHA256：`270F12A7CB8DEED20D1E40AFCC5354AA6CA0D2AD80F714701A0F4F8470D42F2D`
- `PRAGMA integrity_check`：`ok`
- 本任务允许写入可追溯真实采集结果；测试、浏览器写验收和规则开发必须使用隔离数据库。

## Canonical business counts

| Metric | Count |
|---|---:|
| Intelligence（全部） | 31 |
| Intelligence（published、非 demo） | 6 |
| People | 44 |
| Organizations | 24 |
| Projects | 5 |
| Subject Links | 1 |
| Resources | 30 |
| Match Candidates | 0 |
| Opportunities | 11 |
| FollowUps | 4 |
| Relationships | 25 |
| Relationship Evidence | 25 |

## Source

| Status | Count |
|---|---:|
| ACTIVE（healthy + enabled） | 6 |
| CANDIDATE | 4 |
| DISABLED（disabled_by_quality） | 5 |

## Q-BAY and organization context

| Metric | Count |
|---|---:|
| Member Organizations（active/pending membership） | 2 |
| Events | 1 |
| 有 Resource 的 Organization | 6 |
| 有 Canonical Relationship 的 Organization | 10 |
| 有 Opportunity 历史的 Organization | 0 |

## Baseline truth notes

- 11 条 Opportunity 均为既有 demo/manual 记录且没有正式组织主体关联，不能作为 P4 真实主体依据。
- 24 个 Organization 中包含 10 个 `[DEMO]` 组织、1 个 inactive 错误标题主体和若干需人工治理的历史名称；Priority Universe 必须排除 demo，并显式标注数据质量限制。
- 现有明确管理员关注/收藏/标签记录为 0，不为满足 P5 数量伪造关注。
- 现有正式发布且非 demo Intelligence 只有 6 条；R7.2 只使用真实新采集扩样，不复制旧新闻。
