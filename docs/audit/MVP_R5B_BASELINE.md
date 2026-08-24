# MVP-R5B 基线

记录日期：2026-08-24（Asia/Shanghai）

## 正式现场

| 项目 | 值 |
| --- | --- |
| 项目目录 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| Branch | `release/mvp-rc1.2` |
| 起始 HEAD | `ff5ceaa73ff76043d033d791098f546af9094111` |
| 起始 Git status | clean |
| 正式数据库 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db` |
| 任务入口 SHA256 | `A4697537789349B26070A149F6533A19FA5E0525BEE30A220B1F47D428A82951` |
| 任务入口 integrity_check | `ok` |
| 任务入口采集基线 | runs `105/max 108`；items `401/max 404` |

正式核心表入口行数为：情报25、人物44、机构24、资源29、匹配0、机会11、关系25。

## 正式来源

| Source type | 总数 | 启用 |
| --- | ---: | ---: |
| dynamic_page | 1 | 1 |
| list_page | 1 | 0 |
| official_site | 1 | 1 |
| rss | 2 | 2 |
| webpage | 1 | 1 |

共6个来源、5个启用。鲸准虽登记为RSS，实际URL为JS hash应用且robots拒绝；此项只登记，不修改正式业务数据。

## 历史运行结果

109次既有运行按结果归纳为：unchanged 66、success 16、partial 1；历史失败包括旧 `assess_content_quality` 未定义10次、collector不可用4次、robots拒绝2次；历史跳过包括source disabled 6次、stale pending 1次。

这些错误是当前正式库历史记录，不是R5B新运行。R5B真实抓取实测不写数据库，完整smoke仅写OS临时测试库。

## 调度安全准入门

R5A代码只能拒绝pytest下未传 `db_path` 的scheduler，显式传入正式 `data/app.db` 仍可绕过，且可直接调用 `run_collection_cycle()`。R5B在测试任何候选工具前完成最小修复：

- pytest下未显式传库：拒绝；
- pytest下显式传正式库：拒绝；
- pytest下直接运行collection cycle指向正式库：抛出安全错误；
- 显式OS临时测试库：允许注册唯一 `collection_cycle`；
- 全量pytest前后正式来源新增运行0、正式采集记录0。

## 外部遗留实例

任务中发现PID 15940的孤儿Web子进程自13:30起在8000端口运行并每15分钟采集正式EMA。它在14:15产生run 109与items 405–406；确认来源后已停止，8000端口关闭。真实EMA记录按规则保留，未伪造“哈希不变”。隔离冻结点为 SHA256 `53A5C361A861A214C0BFA433EC66DC0831976C99D7E6765C981F5F722C74F6B7`、runs `106/max109`、items `403/max406`、integrity `ok`。

## 候选依赖状态

起始及最终正式 `requirements.txt`、项目venv和生产代码均不含Crawl4AI。PoC仅存在于系统Temp，最终已完整删除。
