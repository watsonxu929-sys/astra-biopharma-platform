---
name: platform-domain-architecture
description: Use when planning, reviewing, or implementing platform-level features for the industrial resource connection platform, especially to classify work into identity, intelligence, network, community, marketplace, or opportunity domains, prevent duplicate domain models, define frontend/backend boundaries, and decide how new features should reuse existing models, services, routes, permissions, search, audit, Worker, and Scheduler capabilities.
---

# Platform Domain Architecture

## 适用场景

- 新增或调整平台功能前判断业务域归属。
- 拆分前台用户体验和内部运营后台。
- 评审模型、服务、路由、页面是否重复建设。
- 设计跨域流程，例如情报信号转招商线索、会员需求转资源市场、活动参与转关系网络。

## 不适用场景

- 只修复单个模板显示、脚本路径或测试断言。
- 只做数据库迁移细节，不涉及业务域边界。
- 只处理具体采集、加工、报告实现，应改用更具体的情报类 Skill。

## 核心原则

- 平台六大核心业务域是：identity、intelligence、network、community、marketplace、opportunity。
- 公共基础域是：auth、permissions、notifications、search、files、audit、taxonomy、scheduling、platform operations。
- 新功能先归域，再选现有模型和服务，最后才考虑新增表。
- 企业、人物、项目、事件、资源、关系、会员、活动、线索、行动、情报、信号、报告默认复用现有能力。
- 前台面向会员、发布者、参与者；后台面向运营、研究、招商、审核和系统管理。

## 执行步骤

1. 阅读 `docs/PLATFORM_ARCHITECTURE.md` 和 `docs/CAPABILITY_REUSE_MAP.md` 的相关域说明。
2. 判断需求主域和辅域：identity、intelligence、network、community、marketplace、opportunity。
3. 查找现有模型、服务、路由、页面和 API，优先复用。
4. 标出跨域调用方式：服务调用、事件/信号来源、审核流、任务队列或 API。
5. 明确前台/后台边界和权限边界。
6. 若需要新增模型，先证明现有模型无法兼容，并说明与现有模型的映射关系。

## 文件范围控制

- 优先查看：`app/models.py`、`app/main.py`、`app/navigation.py`、`app/services/`、`app/api/v1/`、`app/templates/`、`scripts/migrate_*.py`。
- 只看与需求业务域相关的文件名、类名、表名、路由和服务函数。
- 不做无目的全仓扫描，不读取正式数据库内容。

## 数据兼容要求

- 不自动合并同名企业、人物或会员。
- 不重命名历史机器枚举值。
- 不破坏内部 User 登录、会员门户登录、俱乐部会员、正式主体档案和现有权限。
- 跨域新增数据必须保留来源、审核、操作人和回溯路径。

## 禁止事项

- 禁止重复建立企业、人物、会员、资源、机会、关系模型。
- 禁止社区单独建立第二套用户体系。
- 禁止资源市场单独建立第二套企业和联系人。
- 禁止把招商线索、融资需求、采购需求复制成互不关联的模型。
- 禁止单次 Codex 任务同时开发多个业务域。

## 验收标准

- 明确主域、辅域和公共基础域。
- 明确复用哪些现有模型、服务、路由和权限。
- 明确前台和后台边界。
- 明确不新增或确需新增的理由。
- 未引入重复模型、重复导航和重复任务入口。

## 与其他 Skills 的协作关系

- 与 `platform-taxonomy-governance` 协作处理标签、分类、状态和枚举。
- 与 `identity-network-engine` 协作处理 User、Person、Member、Organization 和关系网络。
- 与 `incremental-codex-delivery` 协作控制任务范围、验证范围和交付边界。
- 与 `service-api-separation` 协作保持 Web/API 调用同一服务层。

## 参考文件

- `references/domain-rules.md`
- `references/anti-patterns.md`
- `references/acceptance-checklist.md`
