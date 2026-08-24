# MVP-R3 Migration Dry Run

执行对象：正式数据库只读连接；执行前后 SHA256 均为 `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402`。

命令：

```powershell
python scripts\migrations\mvp_r3_legacy_to_canonical.py --db-path data\app.db
```

## 计划结果

| Domain | Create | Duplicate | Ignore / Archive | Manual review |
|---|---:|---:|---:|---:|
| Relationship | 25 | 0 | 0 | 1 |
| Relationship Evidence | 25 | 0 | 0 | 0 |
| Resource | 9 | 0 | 0 | 0 |
| Match | 0 | 0 | 1张空表 | 0 |
| Opportunity / Lead | 0 | 0 | 3张空表 | 0 |
| FollowUp | 0 | 0 | 无等价数据 | 0 |
| Task | 0 | 0 | actions 7条 ARCHIVE_ONLY | 0 |

- Canonical 新增业务对象合计：34（Relationship 25 + Resource 9）。
- Evidence 新增：25。
- 疑似重复：0。
- 无法解析/外键主体缺失：1。
- 需要人工判断：1。

## MANUAL_REVIEW 决定

`relations.id=18` 的 `source_external_id=PER-20260630-000010` 在当前 people、redirect、merge 和 mapping 中均不存在。禁止按人物顺序、职位文本或名称猜测主体，因此该记录保留 Legacy 只读历史并进入人工复核，不迁入 Canonical。

## 隔离副本演练

- 第一次 apply：`created=34`、`manual_review=1`、`integrity_check=ok`。
- 迁移后行数：Canonical Relationship `25`、Evidence `25`、Canonical Resource `29`。
- 第二次 apply：`created=0`、`duplicates=34`、`duplicate_created=0`、`integrity_check=ok`。
- 失败路径演练曾因开发期 SQL 占位符错误触发整体 rollback；临时库所有目标表保持原行数，验证事务保护有效。错误随后在正式迁移前修复并通过上述两次演练。

Gate 结论：唯一 unresolved 已有明确 `MANUAL_REVIEW` 决定，允许进入备份和正式迁移。
