# 04 Data Model

## 主数据库

默认 SQLite 数据库：

```text
data/app.db
```

实际业务表包括：

- `organizations`
- `people`
- `projects`
- `resources`
- `events`
- `relations`
- `actions`
- `raw_intelligence`
- `import_logs`

## v0.4C 审核表

- `v04c_review_items`: 审核任务。
- `v04c_review_evidence`: 审核证据。
- `v04c_review_actions`: 审核操作历史。
- `v04c_pending_relations`: 待确认关联。
- `v04c_claims`: 事实/推测登记。

## v0.4C-1 接入与事实表

- `v04c1_ingest_batches`: 导入批次。
- `v04c1_source_records`: 来源记录。
- `v04c1_candidates`: 字段或关系候选。
- `v04c1_canonical_facts`: 正式事实库。
- `v04c1_fact_evidence`: 正式事实证据。
- `v04c1_canonical_relations`: 正式关系库。
- `v04c1_sync_mappings`: 业务表映射。
- `v04c1_sync_logs`: 同步日志。

## 事实、推测、待判定

- `fact`: 审核通过后可以进入正式事实库。
- `inference`: 推测层信息，不进入正式事实库。
- `unknown`: 待判定，不进入正式事实库。

只有同时满足“审核状态为 `approved`”和“事实属性为 `fact`”的字段候选，才可以同步为正式事实。

## 版本管理

同一主体、字段的新事实值同步后：

1. 旧当前版本设为非当前。
2. 新值成为当前版本。
3. 历史版本保留。
4. 同值重复同步只追加证据，不创建重复版本。
