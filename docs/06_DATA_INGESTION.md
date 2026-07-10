# 06 Data Ingestion

## 接入口

页面：

```text
/review/intake
```

健康检查：

```text
/review/intake/health
```

## JSON 导入

推荐使用结构化 JSON。示例文件：

```text
examples/v04c1_import_template.json
```

最小结构：

```json
{
  "batch": {"source_name": "source name", "source_type": "manual-json"},
  "records": [
    {
      "external_key": "SOURCE-001",
      "source_url": "https://example.com/article",
      "subject_type": "org",
      "subject_id": "ORG-001",
      "subject_label": "企业名称",
      "fields": [
        {"name": "临床阶段", "value": "II期", "fact_level": "fact", "excerpt": "原文摘录"}
      ]
    }
  ]
}
```

## 批次记录

每次导入会建立批次，记录：

- 批次编号。
- 来源。
- 原始内容。
- 导入时间。
- 操作人。
- 成功、重复、冲突、待结构化、失败数量。

## 去重规则

- 同一来源、同一 `external_key` 不重复写入。
- 没有 `external_key` 时，按来源和内容 hash 去重。
- 同一审核项的相同来源证据不重复追加。
- 重复运行导入不应制造重复审核任务。

## 纯文本处理

没有结构化 `fields` 或 `relations` 的记录会标记为 `needs_structuring`，不会凭空生成正式事实。

## 正式同步

同步入口在 `/review/intake`。只有审核通过且定为 `fact` 的字段候选会进入 `v04c1_canonical_facts`。推测和待判定会停留在候选状态。

## 业务表映射

默认不直接写 `organizations`、`people`、`projects` 等业务表。只有管理员手动建立并启用映射后，系统才会按白名单表名和列名同步字段。
