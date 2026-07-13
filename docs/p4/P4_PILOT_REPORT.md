# P4 受控试点报告

试点批次：`P4-CLUB-OPERATIONS-MVP`。日期：2026-07-13。试点仅在正式库副本上运行，先应用 006，再应用 007；正式 `data/app.db` 未执行迁移或业务写入。

| 项目 | 结果 |
|---|---:|
| 会员 / 机构 | 5 / 2 |
| 活动 / 报名 / 候补 | 2 / 10 / 1 |
| 签到 / 结构化反馈 | 6 / 3 |
| 新需求 / 新供给 | 3 / 3 |
| 资源匹配候选 | 4 |
| 会后关系候选 | 3 |
| ClubLead 候选 | 4 |
| Opportunity | 11，试点前后不变 |

所有试点记录均带 `pilot_batch_id`；正式库 People 44、Organizations 24、Memberships 2、活动档案 1、报名 0、参与 0、统一资源 22、Opportunity 11，试点前后计数和 SHA-256 均一致。验证命令：

```powershell
python scripts/verify_p4_club_operations_mvp.py --db data/app.db --report C:\tmp\p4_pilot_report.json
pytest -q tests/test_p4_club_operations_mvp.py
```
