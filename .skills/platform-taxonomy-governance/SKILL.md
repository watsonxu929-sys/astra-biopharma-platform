---
name: platform-taxonomy-governance
description: Use when adding, reviewing, or refactoring platform labels, categories, enumerations, statuses, Chinese display labels, filters, tags, roles, regions, industry tracks, resource types, demand types, opportunity types, content topics, service capabilities, or any taxonomy-like data; prevents each module from creating its own incompatible label tables or status systems.
---

# Platform Taxonomy Governance

## 适用场景

- 新增资源类型、需求类型、机会类型、内容话题、行业赛道、技术方向、地区、角色或状态。
- 页面需要中文展示标签，而数据库继续保存英文机器值。
- 发现多个模块有相似标签、状态或枚举。

## 不适用场景

- 只修复单条文案。
- 只新增普通业务记录。
- 不涉及分类、筛选、状态、标签或展示映射的功能。

## 核心原则

- 数据库存机器值，前台展示中文。
- 优先复用现有标签和分类，不为单个模块单独建标签表。
- 状态变更必须兼容历史数据。
- 稳定流程状态用枚举；业务可增长分类用可配置 taxonomy。
- 同一概念只能有一个正式中文名和一组机器值映射。

## 执行步骤

1. 识别新增值属于枚举、标签、分类还是状态。
2. 查找现有 `app/i18n`、模型字段、迁移脚本、模板筛选项和 API label 字段。
3. 判断是否复用现有机器值或新增兼容映射。
4. 确认中文展示、API label、筛选项、空状态和报告文案一致。
5. 对历史值保留回退展示，不批量重写正式数据。

## 文件范围控制

- 优先查看：`app/i18n/`、`app/templates/`、`app/api/v1/`、相关 `app/services/`、相关迁移脚本。
- 只搜索目标概念和相邻旧称，不做全仓大替换。

## 数据兼容要求

- 不修改既有英文机器字段名。
- 不破坏历史枚举值和 API 返回字段。
- 新中文 label 通过映射层提供。
- 历史未知值必须安全回退显示。

## 禁止事项

- 禁止每个模块维护一套标签和地区枚举。
- 禁止模板中散落大量 if/else 翻译。
- 禁止把中文展示值写成机器状态。
- 禁止为了新功能重写历史状态。
- 禁止一个概念交替使用多个中文名。

## 验收标准

- 机器值、中文 label、筛选项和页面展示一致。
- 新增分类说明了枚举或可配置 taxonomy 的理由。
- 历史值仍可显示和查询。
- API 保持机器字段，并按需要增加 label 字段。

## 与其他 Skills 的协作关系

- 与 `platform-domain-architecture` 协作判断分类归属业务域。
- 与 `identity-network-engine` 协作处理角色、关系类型和隐私分类。
- 与 `incremental-codex-delivery` 协作控制扫描和验证范围。

## 参考文件

- `references/domain-rules.md`
- `references/anti-patterns.md`
- `references/acceptance-checklist.md`
