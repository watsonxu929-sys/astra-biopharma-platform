# P1 资源迁移冲突人工审核报告

## 冲突概述

迁移脚本 `001_core_domain_unification.py` 在尝试将历史资源/供给记录映射到正式 `v06_market_resources` 时，发现 1 条记录无法唯一匹配。

## 冲突详情

### 冲突记录

| 字段 | 值 |
|---|---|
| 迁移ID | 001_core_domain_unification |
| 领域 | marketplace |
| 来源表 | v04f_club_offerings |
| 来源记录ID | 1 |
| 原因 | unmatched |
| 状态 | pending |
| 创建时间 | 2026-07-10 11:01:04 |

### 旧表记录详情

**表名**: `v04f_club_offerings`

| 字段 | 值 |
|---|---|
| id | 1 |
| offering_no | QBO-20260701-0001 |
| membership_id | 2 |
| title | 会员可提供资源 |
| description | 早期项目评估工艺可行性，识别从科研到生产的风险点，降低转化失败概率 |
| offering_type | 会员资源 |
| industry_tags | (空) |
| region | (空) |
| availability | available |
| status | active |
| related_resource_id | None |
| created_at | 2026-07-01T13:42:54 |
| updated_at | 2026-07-01T13:42:54 |

### 候选匹配

在 `v06_market_resources` 中查找 `direction='supply'` 的记录，未发现标题完全匹配的记录。

### 无法唯一匹配的原因

1. 标题"会员可提供资源"过于通用，无法确定具体对应哪项正式资源
2. 描述内容涉及"早期项目评估工艺可行性"，但正式资源表中没有完全匹配的业务描述
3. 没有 legacy_source_id 或其他唯一标识符可用于精确匹配

## 处理建议

### 选项A：手动映射

需要人工确认该记录应映射到哪条正式 MarketResource，或创建新记录。

### 选项B：保留原样

将该记录标记为"已审核-保留在旧表"，继续通过兼容层读取，不迁移到正式表。

### 选项C：创建新记录

基于旧记录内容在 `v06_market_resources` 中创建新记录，并建立映射。

## 决策

当前状态：**待人工审核**

建议：选项B，保留原样，通过兼容层读取。该记录描述较为通用，创建新记录可能造成重复。

---

## 审核记录

| 审核日期 | 审核人 | 决策 | 备注 |
|---|---|---|---|
| | | | |
