# ASTRA-R1 会员 FK 身份核验与最小修复方案

日期：2026-09-13。范围：只读核验与设计；未执行任何迁移、Schema/正式数据修改或 Git 提交。

## 1. 结论

**FK_SCHEMA_REPAIR = GO（仅方案可行；不是执行授权，也不是全库 FK 已修复）。**

CANONICAL_MEMBERSHIP_TABLE = `v04f_club_memberships`。
四表全部 5 行共引用 2 个唯一会员 ID：`{1,2}`，全部为 EXACT_IDENTITY_MATCH。
按唯一会员统计：EXACT=2，REMAP=0，AMBIGUOUS=0，MISSING=0，SEMANTIC_CONFLICT=0。
按引用行统计：EXACT=5，其余类别均为0。CSV一行对应一条真实子记录，没有遗漏非报错记录。

不改任何 membership_id 值，仅将四表的 Membership FK Target 从
`v04f_club_memberships_old(id)` 改回 `v04f_club_memberships(id)`。
不更改会员、人物、企业、账户、通知、联系方式、Offering 数据及业务代码。
GO仅对已核实的会员记录连续性成立，不认证历史企业资料的现实真实性。

## 2. 正式事实来源与迁移原因

- 当前 sqlite_master 中存在唯一 `v04f_club_memberships` 正式会员表；`v04f_club_memberships_old` 不存在。
- `app/main.py:116` 注册 `app/v04f_operations.py`；其中 `/club/members`（691行起）直接查询正式会员表，并关联 people / organizations。
- `app/services/membership_access_service.py:50` 的统一会员查询读取该表的 member_no、user_id、person_id、organization_id、member_level、status。
- `app/api/v1/clubs.py:91` 的会员状态接口与 Web `/club/members/{id}/lifecycle` 均调用 `ClubMembershipService.transition_membership`，更新同一张表。
- `scripts/migrate_membership_person_link_v1.py:88-137` 为允许人物暂未绑定，将原会员表重命名为 _old，逐列复制原 id、会员编号、人物/企业、角色、状态、来源和时间字段至同名新表，再移除 _old。_old 是迁移暂存表，不是另一套会员事实源。
- 迁移未重建引用会员的子表；现代 SQLite 的 RENAME 会改写外部 FK target，解释了四表保留 _old 引用的现状。脚本还在 BEGIN 之后切换 foreign_keys，此位置不能可靠改变外键执行开关。此次只读，不重跑旧脚本。
- 历史备份链定位到 2026-07-03：11:31:36/11:32:39命名的备份仍为 person_id NOT NULL、子表指向原表；12:47:35命名的备份已为 nullable。缺少独立执行日志，精确执行时刻 UNKNOWN；文件命名只作为时间范围旁证。Git中的2026-07-10基线提交日期不是迁移发生日期。

## 3. 身份证据链

|会员映射|唯一会员编号|人物稳定键|企业稳定键|独立导入结果|
|---|---|---|---|---|
|1 → 1|QBM-20260630-0001|23 / PER-20260630-000017|13 / ORG-20260630-000001|job 2 / QBI-20260630-0002；draft 22 的 saved_person_id=23、saved_organization_id=13、saved_membership_id=1|
|2 → 2|QBM-20260701-0001|24 / PER-20260701-000001|14 / ORG-20260701-000001|job 3 / QBI-20260701-0001；draft 24 的 saved_person_id=24、saved_organization_id=14、saved_membership_id=2|

核验不是只比较主键：

1. 与迁移前备份逐字段比较，两条会员记录的全部原有列值一致；会员编号各自唯一，member_level=standard、status=active、expired_at/deactivated_at为空。
2. 角色分别为空字符串、总监；创建/加入/更新时间分别为2026-06-30T16:08:39和2026-07-01T13:42:54，均原样保留。
3. 两个人物的姓名、external_id、来源编号、来源类型、创建时间一致；两个企业的external_id、来源编号、来源类型和创建时间一致，稳定键各自唯一。
4. 两项原始导入job仍为completed；已保存draft、人员/企业/会员三元映射、来源编号与迁移前完全一致。这两位通过人工导入建会，没有关联的新会员申请/审批记录，不能补造申请链。
5. 四张子表的所有5行，与迁移前备份逐字段相等，包括编号和时间字段。敏感字段只在内存比较，不输出内容。
6. 旧表没有user_id列；后续 `scripts/migrate_user_membership_link_v1.py:42` 仅新增可空user_id。两条当前值均为NULL，后续备份同样为NULL，针对这两位的用户/人物绑定审计及会员状态历史均0条。CSV明确标注“不适用/未绑定”，不把缺失信息伪报成用户相等，也不将member_1用户名映射到平台User。
7. Account #1、QBACC-20260630-0001始终属于会员1，状态invited；会员状态active是另一种状态，二者不冲突。account_no、membership_id、username分别UNIQUE，单账户只能属于一个非空会员，每会员最多一个该类账户。
8. 两位均属于既有Q-BAY会员；无可靠tenant字段，未推断入驻身份。

### 企业资料边界

企业13当前名称“待核对”，企业14当前名称“待核”；原名称分别是履历句子和匿名企业描述，org_type也从SQL NULL变成了文本“None”。
`docs/audit/MVP_R7_5_SUBJECT_IDENTITY_AUDIT.csv` 已分别记录 WRONG_ENTITY 与 INSUFFICIENT_DATA。
这不是新的会员映射冲突：两条会员与导入draft始终指向同一内部企业记录，稳定外部编号及来源不变，没有发现转绑到另一企业的证据。
本次EXACT表示历史会员及其内部关联的连续性，不表示上述企业已完成法律主体核验。CSV的organization_match明确保留该限制；不改名、不换绑、不纠正这些历史主数据。

## 4. 全部引用与必须保留的结构

|表|全部行数|唯一会员数|min/max|membership_id|其他FK|UNIQUE / CHECK|显式索引 / 触发器|
|---|---:|---:|---|---|---|---|---|
|v05b_member_contacts|2|2|1/2|INTEGER NOT NULL UNIQUE|source_job_id → v05b_import_jobs.id|membership_id唯一；无CHECK|email、mobile索引 / 0|
|v04f_club_offerings|1|1|2/2|INTEGER NOT NULL|无|offering_no唯一；无CHECK|0 / 0|
|v05d_member_accounts|1|1|1/1|INTEGER NOT NULL UNIQUE|无|account_no、membership_id、username各自唯一；status五值CHECK|status、updated_at DESC组合索引 / 0|
|v05d_member_notifications|1|1|1/1|INTEGER NOT NULL|无|notification_no唯一；category八值及status三值CHECK|membership_id、status、created_at DESC组合索引 / 0|

四个错误Membership FK以及contacts的source_job_id FK均为 **ON DELETE NO ACTION / ON UPDATE NO ACTION / MATCH NONE**，没有声明延迟约束。保持不变，不改CASCADE、SET NULL。
四表均为INTEGER PRIMARY KEY AUTOINCREMENT；原高水位分别2、1、1、1，必须保留，禁止复用历史ID。
完整当前CREATE TABLE及4条显式索引定义见附录。6个UNIQUE自动索引由原约束重建，保留唯一列、排序与BINARY排序规则，不手写sqlite_autoindex。

外部入向引用必须保留：
- v04f_club_matches.offering_id → v04f_club_offerings.id（当前0行）。
- v05d_activation_tokens.account_id → v05d_member_accounts.id（当前1行，必须原样保留，不展示凭据）。
- v05d_password_reset_requests.account_id → v05d_member_accounts.id（当前0行）。
- 当前没有引用四表的视图或触发器。后续执行前必须重新枚举，不能沿用过期结论。

正式会员管理使用activate/suspend/resume/expire/withdraw状态迁移，不物理删除会员；错误主体解绑也保留会员行并记录历史。
因此维持NO ACTION符合保留历史的语义；停用/退出不应删除联系人、账户、通知或Offering。

## 5. 仅拟定的最小执行方案

本机项目Python连接的SQLite版本为 **3.50.4**，不支持直接ALTER一个FK Target；采用标准表重建。
仅设计以下顺序，**本阶段没有执行，未创建迁移脚本，未进行任何库的重建演练**。

1. PRECHECK：取得新的明确执行授权；安排维护窗口停止Web/Worker等写入，重新核验身份、5条引用、4表DDL、外部引用、全部FK违规集合及高水位。任何新增/变化记录重新分类，未满足EXACT即停止。
2. BACKUP VERIFY：使用SQLite Backup API在维护窗口取得新的一致性备份，校验integrity、FK清单、SHA256。已有备份保留，不用历史普通copy备份作为正式修复回滚点。
3. 专用维护连接在事务外设置foreign_keys=OFF并核实为0，然后 BEGIN IMMEDIATE。不是全局关闭，也不改变应用连接配置；不能先BEGIN再OFF。
4. 依次重建 contacts → offerings → accounts → notifications，四表处于同一个事务：
   - 逐表从当时sqlite_master原DDL派生 `<table>__astra_r1_new`；只替换CREATE表名及唯一的Membership REFERENCES target，其他文本/约束不变。
   - 使用明确的全列清单复制数据，保留NULL、空字符串、账户密文、所有主键和membership_id值；不用SELECT *隐式猜测列顺序，不输出敏感字段。
   - 在移除旧表之前比较行数、主键集合、逐列值/类型和空值分布；检查新表FK、UNIQUE/CHECK及所有关键关系。
   - 再移除旧表，将新表改回原名；恢复原显式索引。**禁止先将旧表RENAME为临时名**，以免再次污染外部FK Target。
   - 恢复并核验AUTOINCREMENT原高水位；不允许低于原值。原表名最终不变，入向FK定义不变。
5. restore indexes/triggers：当前4条显式索引、6个UNIQUE自动索引、0触发器；按执行前快照复核全部属性。保留外部三个引用表的结构及数据。
6. COMMIT前验证：
   - 四表row_count仍为2/1/1/1；逐列值和5个membership_id完全一致，所有关联表和Canonical会员记录未变。
   - schema允许差异只有4处Membership FK target；columns/types/NOT NULL/DEFAULT/PK/AUTOINCREMENT/UNIQUE/CHECK/indexes/triggers及其他FK全部等价。
   - 四表foreign_key_check必须0行；全库FK集合必须等于执行前集合减去这5条，其他25条原样保留。按当前基线预计30 → 25，绝不以本子任务宣称全库FK=0。
   - integrity_check必须ok；没有__astra_r1_new残留。任一条件失败执行ROLLBACK，四表一起回滚，禁止部分提交。
7. 全部检查通过后COMMIT；事务结束后恢复foreign_keys=ON并核实为1，关闭维护连接。在新的FK启用连接复核只读结果，取得修复后SQLite Backup API备份，再恢复原运行方式。
8. COMMIT之前失败使用事务ROLLBACK。提交后如发现异常，停止写入并以维护窗口一致性备份进行经授权恢复；禁止在线直接覆盖app.db或忽略WAL。恢复方案需保护维护窗口之后的新增业务写入。

事务边界不得使用会隐式提交的脚本执行方式拆开；执行工具应逐条execute并统一commit/rollback。
该方案保留Schema和业务值，GO为静态设计结论；运行验证仍是获得后续授权后提交事务的必要条件。
SQLite官方依据：[通用ALTER重建步骤及重命名风险](https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes)、[外键开关须在事务外设置](https://www.sqlite.org/foreignkeys.html#fk_enable)。

## 6. 备份、只读保障与交付边界

- 正式库：`E:/Codex项目设计/招商一体化平台系统/biopharma-intelligence-mvp-rc1/data/app.db`。所有本阶段数据库连接均使用URI `mode=ro`，未调用可能自动建Schema的Web/Service入口，未启动Web、运行测试或Migration。
- 本阶段核验前后：integrity=ok，foreign_key_check=30，schema_version=826。正式库文件SHA256：`d0dd10b1f7135cb06804cc1a91c99fcce50ab90f55d7d4f9d7aecff87f039267`。
- 前阶段一致性备份：`data/backups/ASTRA_R1_PRE_DATA_TRUST_20260913_225006.db`，SHA256 `1c4a5cb40cde90a9fb1d7d89c3e77d33b5099e8b8ffaf05eed869d3f11733b8e`，只读验证integrity=ok、FK=30。该文件与活动库物理哈希不同，不以物理哈希相等假定逻辑数据相等。
- 历史身份证据：`data/backups/app_before_membership_person_link_v1_20260703_113136.db`，SHA256 `6d4df074f8f9d423dffe5808d58688ac23a9bffe5dea1ecfbae495f4b651961d`，integrity=ok；11:32:39备份同哈希。此旧脚本使用copy生成的备份只作所见记录的历史证据，不宣称完整WAL快照，不作本次恢复基线。
- 后续会员备份交叉核对：12:47:35/12:47:53/12:55:41备份哈希相同为`c55628a481083ce0bb6829038737f64363403b188e031ef19d597c2f369edbf5`；15:41:38备份为`65542b4048b2867027f31d8ffce6fefeabe80228bc8bead9873d6f75d0ec9815`，均integrity=ok。两会员字段及5条子记录连续保留。
- Branch=`release/mvp-rc1.2`；HEAD=`3a491a5b61632b9531f08f5453e66978444398e5`。原39项G/H文件保持不变；本阶段只新增本Markdown及同目录 `ASTRA_R1_MEMBERSHIP_FK_MAPPING.csv`。
- 按项目交付守护规则只读保全，按表格规则区分缺失值/不适用与已证明匹配；不输出密码、Token或联系方式。未处理其余25条FK，不进入ASTRA-R2。

## 附录：当前原始表结构（只读抄录，不是可执行修复脚本）

所有未在语句中声明的DEFAULT保持无显式默认值；所有当前触发器数量为0。实际执行仍须从当时sqlite_master重新取值并比对，不能盲用本附录覆盖新变更。

### v05b_member_contacts

```sql
CREATE TABLE v05b_member_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id INTEGER NOT NULL UNIQUE,
    mobile TEXT,
    email TEXT,
    wechat TEXT,
    preferred_contact_method TEXT,
    source_job_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES "v04f_club_memberships_old"(id),
    FOREIGN KEY(source_job_id) REFERENCES v05b_import_jobs(id)
);
CREATE INDEX ix_v05b_contacts_email
ON v05b_member_contacts(email);
CREATE INDEX ix_v05b_contacts_mobile
ON v05b_member_contacts(mobile);
```

### v04f_club_offerings

```sql
CREATE TABLE v04f_club_offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offering_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    offering_type TEXT,
    industry_tags TEXT,
    region TEXT,
    availability TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    related_resource_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES "v04f_club_memberships_old"(id)
);

```

### v05d_member_accounts

```sql
CREATE TABLE v05d_member_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'invited',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    activated_at TEXT,
    last_login_at TEXT,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    session_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    FOREIGN KEY(membership_id) REFERENCES "v04f_club_memberships_old"(id),
    CHECK(status IN ('invited','active','locked','suspended','deactivated'))
);
CREATE INDEX ix_v05d_member_accounts_status
ON v05d_member_accounts(status, updated_at DESC);
```

### v05d_member_notifications

```sql
CREATE TABLE v05d_member_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    related_type TEXT,
    related_id TEXT,
    status TEXT NOT NULL DEFAULT 'unread',
    read_at TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY(membership_id) REFERENCES "v04f_club_memberships_old"(id),
    CHECK(category IN ('account','profile','event','matching','need','offering','review','system')),
    CHECK(status IN ('unread','read','archived'))
);
CREATE INDEX ix_v05d_notifications_member
ON v05d_member_notifications(membership_id, status, created_at DESC);
```
