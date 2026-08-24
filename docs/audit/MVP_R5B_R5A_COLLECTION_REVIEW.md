# MVP-R5B 对 R5A 正式采集记录复核

记录日期：2026-08-24（Asia/Shanghai）

## 范围

复核正式Source 4 `EMA News RSS` 在遗留Web/Scheduler运行100–109生成的collection items 387–406，共20条、2个真实EMA URL、6个不可变snapshot。20条质量状态均为accepted。

## 分类

| 结论 | IDs | 数量 | 理由 | 处理 |
| --- | --- | ---: | --- | --- |
| KEEP_REAL_CHANGE | 388, 399, 400, 402, 404 | 5 | 真实EMA详情内容被现有hash规则判为changed；均进入pending processing job 28–32 | 保留，不强制发布 |
| KEEP_DEDUP_AUDIT | 387, 389–398, 401, 403, 405, 406 | 15 | 同URL/同内容由既有规则标记unchanged、ignored并建立duplicate链 | 保留审计链，不机械删除 |
| DELETE_TEST_OR_ERROR | 无 | 0 | 没有测试marker、虚假Source、抓取错误正文或验收账号数据 | 不删除 |

## 真实性与下游状态

- URL均属于 `www.ema.europa.eu/en/news/...`，标题分别为EMA领导团队任命和CHMP会议要点。
- 10次运行中success 4、unchanged 6；累计changed 5、duplicate 15、failed 0。
- 5条changed记录仅形成pending processing job；extraction candidate 0、正式Intelligence 0。
- R5B没有运行Worker、没有审核、没有发布、没有写Canonical业务表。
- items 405–406来自已确认的遗留孤儿Web进程14:15定时运行，不是pytest或R5B smoke；该进程已停止。

## 结论

20条均是需要保留的真实来源证据或去重审计记录；建议继续由现有去重/处理状态机管理。当前可直接删除记录为0，本任务未删除或修改任何正式记录。
