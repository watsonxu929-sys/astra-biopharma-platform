# MVP-R3 R2 Diff Scope Gate

审计对象：`ce470ad95b86e69a1e7eb03293bbfa7f9a12348a`（`MVP-R2 canonical single-write consolidation`）

## 可复现统计口径

任务说明中的 `+2496 / -0` 无法由该 Git 提交复现。以 `git show --numstat ce470ad...` 为唯一可复现口径，R2 实际为：

| 分类 | +LOC | -LOC | 说明 |
|---|---:|---:|---|
| Production 业务代码（既有 Service） | 480 | 704 | Single Write owner、事务提交边界和重复 Writer 删除 |
| Route / Adapter | 82 | 173 | 既有路由、Q-BAY 和会员/活动适配入口委托给 Owner |
| Tests | 111 | 0 | R2 Single Write Contract |
| Audit docs | 294 | 0 | 基线、Before/After Map、结果 |
| Fixtures | 0 | 0 | 无 |
| Compatibility | 0 | 0 | 无新增兼容层 |
| 其他 | 0 | 0 | 无 |
| **合计** | **967** | **877** | 与 Git stat 一致 |

Production 新增 LOC 为 `480`；全部运行时代码新增为 `562`。运行时代码净变化为 `-315`。

## Scope Gate 结论

- 新增 `CanonicalRelationshipService` 1 个，系 Relationship/Evidence 唯一 Write Owner 的必要收口；没有第二个同域 Service。
- 新增 Repository、Registry、Command Bus、第二套路由体系：均为 0。
- 没有新增业务 Model、数据库表、依赖或版本目录。
- 主要增量由 Owner 委托、tests 和 audit docs 构成，同时删除了更多重复 Writer 代码。

结论：`NO_R2_SCOPE_VIOLATION`，允许继续 R3。
