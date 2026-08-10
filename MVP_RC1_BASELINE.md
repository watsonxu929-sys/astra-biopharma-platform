# MVP-RC1 存量恢复基线

- 原项目路径：`E:\\Codex项目设计\\招商一体化平台系统\\biopharma-intelligence-starter`
- RC1稳定副本：`E:\\Codex项目设计\\招商一体化平台系统\\biopharma-intelligence-mvp-rc1`
- 恢复源分支：`rescue/trae-4day-usable-mvp`
- 恢复源HEAD：`ba8d653523beffcf916f7cb14ae22e46dd6bab4d`
- 恢复源状态：52项未提交修改；原目录保持只读
- RC1开发分支：`feat/mvp-rc1-golden-loop`
- 基线日期：2026-08-10（Asia/Shanghai）

## 永久恢复材料

- 源码快照：`..\\MVP_RC1_RECOVERY\\CURRENT_SOURCE_SNAPSHOT.zip`
- 源码快照SHA256：`7B9DB4A223EA1F7B489536067453F4330C1AFAD753130EFA13F151AD6A6B5B32`
- 数据库备份：`..\\MVP_RC1_RECOVERY\\app_before_mvp_rc1.db`
- 数据库备份SHA256：`DAEAE625F4B2A78DCECF21CC35DD41B4787AD79E3D729F705C43122C5D8B7330`
- RC1数据库工作副本SHA256：`A28E2DE7B71E608931088B262D6304B0426954CE0C064185C4133A38ED63D138`
- SQLite完整性：`ok`
- 历史外键问题：30项（本轮只记录，不清理）
- 当前表数量：188

## 核心表记录数

| 表 | 数量 |
|---|---:|
| v06_intelligence_items | 25 |
| v05f_collection_items | 383 |
| v04g_monitoring_sources | 6 |
| v04g_monitoring_runs | 96 |
| people / organizations / projects | 44 / 24 / 5 |
| v06_market_resources | 20 |
| v06_opportunities | 11 |
| v06_follow_ups / v06_collab_tasks | 4 / 4 |
| relations（Legacy） | 26 |
| core_intelligence_subject_links | 0 |
| p4_resource_match_candidates | 0 |
| p3_canonical_relationships / p3_relationship_evidence | 0 / 0 |

## 基线声明

历史CORE-0.6T/U提交对象未能直接恢复。MVP-RC1不伪造历史版本，正式以“当前存活代码 + 当前存活数据库”建立新基线。数据库禁止降级、重建或删除既有字段；开发与测试仅使用RC1副本及测试副本。
