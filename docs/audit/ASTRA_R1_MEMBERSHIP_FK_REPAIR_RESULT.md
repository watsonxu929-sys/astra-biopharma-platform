# ASTRA-R1 Membership FK Repair Result

执行日期：2026-09-13（Asia/Shanghai）。范围：CONTINUE-2 授权的四表 Membership FK 结构修复；不是 ASTRA-R1 全部完成。

## 结果

- foreign_key_check：**30 → 25**；修复后集合严格等于修复前集合减去批准的 5 条，其他 25 条保留原状。
- 四表 FK 检查均为 0；integrity_check 在提交前、提交后新连接和两份备份中均为 ok。
- 唯一语义 Schema 变化：下列四表 membership_id 的目标由 v04f_club_memberships_old(id) 改为 v04f_club_memberships(id)。
- SQLite RENAME 自动为 CREATE TABLE 的表名增加双引号；比较时仅规范化此等价引号，不视为额外结构变化。

| 表 | 修复前/后行数 | 保持原样的 record_id → membership_id |
| --- | --- | --- |
| v05b_member_contacts | 2 / 2 | 1 → 1；2 → 2 |
| v04f_club_offerings | 1 / 1 | 1 → 2 |
| v05d_member_accounts | 1 / 1 | 1 → 1 |
| v05d_member_notifications | 1 / 1 | 1 → 1 |

## 安全核验与执行

- 执行前重新确认 Branch/HEAD、39 项 G/H 文件哈希、身份映射、DDL、索引、触发器、入向 FK 与已批准基线一致。
- 2 个会员 / 5 条引用仍为 EXACT_IDENTITY_MATCH；这是会员记录身份连续性，不代表企业法律身份已核实。
- 维护窗口未发现运行中的 Web、Worker、Scheduler 或采集写进程；8000 无监听，Restart Manager 对 DB 及存在的 sidecar 返回空进程列表。旧 web.pid 无对应进程，未修改；本轮无须停止或重启应用。
- 专用维护连接在事务外确认 foreign_keys=0，单次 BEGIN IMMEDIATE 按上述表顺序执行 CREATE new → 显式列名复制 → 全列校验 → DROP 原表 → RENAME 新表 → 恢复显式索引。
- 每表 DROP 前核验行数、主键、全部列值、NULL 分布、存储类型及 membership_id 一致；没有先重命名原表。
- 保持字段顺序、类型、默认值、NOT NULL、PK、AUTOINCREMENT、UNIQUE、CHECK、其他 FK、排序及 COLLATION。4 个显式索引、6 个 UNIQUE 自动索引语义保持；触发器与入向 FK 保持。
- 所有业务表完整数据比较一致，Canonical Membership 不变；整个 sqlite_sequence 不变，四表高水位保持 2 / 1 / 1 / 1。无临时重建表残留。
- 提交前全部检查通过后仅一次 COMMIT；随后恢复并读取 foreign_keys=1，关闭维护连接。新只读连接显式开启 foreign_keys 后再次验证通过；该设置为连接级，不声称全局持久化。
- 正式库未发生 ROLLBACK。执行前仅在内存副本演练过主动回滚，并验证恢复原状。
- 最终独立复核：PRE/POST/正式库全部表数据与序列相同；POST 与正式库 Schema 相同；PRE → 正式库仅四个批准目标变化；索引、入向 FK 不变。

## 一致性备份

两份均通过 SQLite Backup API 创建，核验源/备份完整逻辑数据及 Schema 一致；未以简单文件复制代替。

PRE（本次直接回滚点；integrity_check=ok，FK=30）：

- 路径：E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_PRE_MEMBERSHIP_FK_REPAIR_20260913_232331.db
- SHA256：1c4a5cb40cde90a9fb1d7d89c3e77d33b5099e8b8ffaf05eed869d3f11733b8e

POST（integrity_check=ok，FK=25）：

- 路径：E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\backups\ASTRA_R1_POST_MEMBERSHIP_FK_REPAIR_20260913_232331.db
- SHA256：5efd6c6cbee310f09a82b6a2100c6a6cd392077f3492c33ed4a5deeafe80bfef

## 范围与工作区

- 产品 Python、Template、Service、Model、Migration 本轮修改均为 0；未新增业务表、长期脚本或框架。未运行 pytest、浏览器业务操作或历史迁移链。
- Branch：release/mvp-rc1.2；HEAD：3a491a5b61632b9531f08f5453e66978444398e5；未提交 Git。
- 原 39 项 G/H 未提交修改校验值完全保持；此前 Mapping CSV 与 Repair Plan 未改。本轮只新增本结果及 ASTRA_R1_DATA_CHANGES.csv 两份审计文件，工作区保持未提交。
- CSV 的 5 行表示修复结构后恢复有效的原引用，不表示对这 5 行执行业务值更新或删除。
- 剩余 25 条 FK 未处理。建议另获授权后在 ASTRA-R1 continuation 中单独分类；不进入 ASTRA-R2。
