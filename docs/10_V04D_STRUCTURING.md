# v0.4D-A 原始情报结构化工作台

## 定位

v0.4D-A 位于“来源接入”和“数据审核”之间，用于处理纯文本来源。

```text
原始情报
→ 来源收件箱
→ 结构化草稿
→ 结构化复核
→ 数据审核队列
→ 正式事实同步
```

## 核心对象

### 结构化任务

一条来源只建立一个结构化任务，防止重复加工。任务状态包括：

- `draft`：草稿；
- `ready`：待结构化复核；
- `returned`：退回修改；
- `submitted`：已送数据审核；
- `partial`：部分送审失败；
- `cancelled`：已取消。

### 结构化条目

支持三类：

- `field`：主体字段候选；
- `relation`：主体关系候选；
- `event`：事件候选。

每条条目必须绑定原文证据摘录。

## 安全边界

1. 结构化不是事实确认。
2. 结构化任务不能直接写正式事实库。
3. 关系候选先按推测进入待确认关联。
4. 事件拆分为多个字段审核项。
5. 送审后的成功条目锁定，避免静默改写。
6. 同一来源只建立一个任务；同一任务不能重复送审。

## 主要页面

```text
/review/structure
/review/structure/tasks/{task_id}
/review/structure/health
```

## 数据表

```text
v04d_sequence_counters
v04d_structuring_tasks
v04d_structure_items
v04d_task_actions
```

## 与既有模块的关系

- 来源来自 `v04c1_source_records`；
- 字段候选通过 `process_field_candidate` 进入 v0.4C；
- 关系候选通过 `process_relation_candidate` 进入待确认关联；
- 事件候选被拆解为多个字段候选；
- 后续正式事实同步仍由 v0.4C-1 完成。
