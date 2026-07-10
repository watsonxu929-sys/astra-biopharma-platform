# v0.4C-1 JSON 数据格式

## 推荐完整格式

```json
{
  "batch": {
    "source_name": "企业官网与公开报道",
    "source_type": "manual-json",
    "note": "本批次说明"
  },
  "records": [
    {
      "external_key": "website-20260628-001",
      "title": "某企业完成B轮融资",
      "source_url": "https://example.com/article",
      "source_grade": "B",
      "published_at": "2026-06-28",
      "subjects": [
        {
          "subject_type": "org",
          "subject_id": "ORG-001",
          "subject_label": "某某生物",
          "fields": [
            {
              "name": "融资轮次",
              "value": "B轮",
              "fact_level": "fact",
              "confidence": 0.95,
              "excerpt": "公司宣布完成B轮融资"
            }
          ]
        }
      ],
      "relations": [
        {
          "left_type": "person",
          "left_id": "PER-001",
          "left_label": "张三",
          "relation_type": "创始人",
          "right_type": "org",
          "right_id": "ORG-001",
          "right_label": "某某生物",
          "confidence": 0.8,
          "basis": "报道中称张三为公司创始人"
        }
      ]
    }
  ]
}
```

## 字段说明

- `external_key`：该来源中的唯一编号。相同来源名和相同 external_key 不重复处理。
- `source_grade`：建议使用 A、B、C、D。
- `subject_type`：建议统一为 `org`、`person`、`project`、`event`、`resource`。
- `subject_id`：尽量填写系统已有正式编号。业务表映射依赖该值定位记录。
- `name`：字段名，例如临床阶段、融资金额、所在地。
- `value`：来源提供的候选值。
- `fact_level`：只能使用：
  - `fact`：来源明确陈述，但仍需审核；
  - `inference`：推测或估算；
  - `unknown`：暂时无法判定。
- `confidence`：0 到 1，仅作为审核参考，不代替人工判定。
- `excerpt`：支持该候选值的原文摘录。

## 自动分类结果

- `new_pending`：正式事实库无该字段，生成事实核验任务。
- `matched_fact`：与现有正式事实一致，不新增审核任务，但保留来源候选。
- `conflict_fact`：与正式事实冲突，生成多来源冲突任务。
- `duplicate_candidate`：与尚未完成的候选值相同，合并审核项并追加证据。
- `conflict_candidate`：尚无正式事实，但不同来源候选值互相冲突。
- `inference_pending`：推测，进入审核但禁止直接同步。
- `relation_pending`：待确认关联。
