# ASTRA-CLOSEOUT-02

审核可用性已收口，但PC冻结未通过：Event #7仍有活跃写入风险，不能为了冻结把它降为普通历史债务。

TASK_NAME = ASTRA-CLOSEOUT-02
STATUS = CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING（冻结阻断，不代表产品全就绪）
BRANCH = release/mvp-rc1.2
HEAD = 3a491a5b61632b9531f08f5453e66978444398e5
REVIEW_ACCEPTANCE = PASS
REVIEW_ITEMS_CHECKED = 10
REVIEW_P1_FIXED = 2
EVENT_7_DECISION = FREEZE_BLOCKER
WORKTREE_TOTAL = 92
WORKTREE_INCLUDE = 92
WORKTREE_EXCLUDE = 0（Git清单；ignored数据库/凭据/临时产物全部排除）
WORKTREE_UNKNOWN = 0
DB_SHA256_BEFORE = c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d
DB_SHA256_AFTER = c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d
SCHEMA_HASH_BEFORE = 312fac35f228a7ba7af8a8ceb70a1f578b716ba38c954fa5f7ed122c5dc5d35d
SCHEMA_HASH_AFTER = 312fac35f228a7ba7af8a8ceb70a1f578b716ba38c954fa5f7ed122c5dc5d35d
TABLE_COUNT_BEFORE = 200
TABLE_COUNT_AFTER = 200
TABLE_COUNT = 200
DB_INTEGRITY = ok
TARGETED_TESTS = 34/34（6展示/地点、13 R3事实、9 R2主线、2运行边界、4私有可见性）
CHROMIUM_RESULT = PASS / 151.0.7922.34 / 1440×900
P0_OPEN = 0
P1_OPEN = 1（Event活跃API及FK兼容关闭路径）
P2_DEFERRED = 8
P3_DEFERRED = 2
PC_V1_FREEZE_READY = NO
NEXT_STAGE = 等待最小活动写保护修复授权，不进入API开发

## 两项最小审核P1

1. 重复摘要被多次展示为不同事实，缺少有效事实时仍堆叠占位，影响审核判断。新增仅展示宏_review_facts：保留有证据的不同内容、摘要不重复，缺证据明确“事实抽取不足，请查看原文”；原文链接可见；忽略原因按需展开；发布文案清晰。未改状态机、发布门槛、Schema或来源。
2. 真实样本#366把Citi会议与后一场H.C.Wainwright的Lotte地点拼接：现有正则venue误命中Avenue，且未匹配Location。仅修event地点表达式英文词边界并识别Location，回归确认首场JW Marriott Essex House，不再串到Lotte。没有新增行业分类或通用抽取体系。

## 10条当前真实待审样本

来自42条既有队列，按当前类别分组取首条，覆盖10种当前规则类别；规则类别不是已确认事实，例如ESG不冒称人事变动。没有采集或补造样本。逐条人工式阅读当前保存正文/来源/时间证据，浏览器实际进入详情并展开正文。PASS表示可以合理决定发布/忽略/补证，不表示10条都可发布或全部字段完美。

|候选ID|WHO|WHAT|WHEN|WHY_IT_MATTERS|SOURCE|NEXT_ACTION|修复前|修复后|
|---|---|---|---|---|---|---|---|---|
|319|药明生物|入选Forbes China ESG50（标题）；正文混入导航|9月16日披露，非任职事件|公司ESG动态，不能据leadership关键词认定人事变动|[WuXi Biologics](https://www.wuxibiologics.com/press-release/wuxi-biologics-named-to-forbes-china-esg-50-list-2026-for-green-crdmo-and-digital-esg-leadership)|忽略；需取得对应正文才考虑重新审核|FAIL|PASS|
|345|复宏汉霖/Getz Pharma|汉达远获巴基斯坦上市批准|9月16日披露；正文称2026年9月获批|已有产品的海外准入进展|[Henlius](https://www.henlius.com/NewsDetails-31569-26.html)|可核对原文后发布；隔离UI已执行|PARTIAL|PASS|
|386|信玖凝研发企业/天津用药患者|血友病B基因治疗全国首方|8月24日事件；9月14日披露，不混用|真实商业化/治疗落地；不能当作新临床试验启动|[启明创投投资企业新闻](https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E5%8D%95%E6%AC%A1%E6%B2%BB%E7%96%97%EF%BC%8C%E9%95%BF%E6%9C%9F%E8%8E%B7%E7%9B%8A%EF%BC%9A%E4%BF%A1%E7%8E%96%E5%87%9D%C2%AE%E5%85%A8%E5%9B%BD%E9%A6%96%E6%96%B9%E8%90%BD%E5%9C%B0%EF%BC%8C%E8%A1%80%E5%8F%8B%E7%97%85b%E8%AF%8A%E7%96%97%E6%AD%A5%E5%85%A5%E5%9F%BA%E5%9B%A0%E6%B2%BB%E7%96%97%E6%97%B6%E4%BB%A3)|可作为产业动态保留；临床类型为规则建议|PARTIAL|PASS|
|396|杭州佳量脑科学、启明创投|C及D轮合计数亿元，启明领投C轮|9月8日披露；事件为近日，未造精确日期|融资轮次、投资方和用途可核实，不是自动商机|[启明创投投资企业新闻](https://www.qimingvc.com/cn/news/%E5%90%AF%E6%98%8E%E6%98%9F-%E4%BD%B3%E9%87%8F%E8%84%91%E7%A7%91%E5%AD%A6%E8%BF%9E%E7%BB%AD%E5%AE%8C%E6%88%90c%E8%BD%AE%E5%8F%8Ad%E8%BD%AE%E4%B8%A4%E8%BD%AE%E8%9E%8D%E8%B5%84%EF%BC%8C%E5%90%AF%E6%98%8E%E5%88%9B%E6%8A%95%E9%A2%86%E6%8A%95c%E8%BD%AE)|可核对后发布，不将合计金额分配给单轮|PARTIAL|PASS|
|366|亚盛医药管理团队|参加四场投资者会议|9月2日披露；场次日期为9/9、9/14、9/16–17、9/23–24|了解资本市场沟通安排，不能混配场次地点|[Ascentage Pharma](https://ascentage.com/ascentage-pharma-to-participate-in-four-upcoming-investor-conferences)|核对各场次后决定收录；地点串联P1已修|FAIL|PASS|
|199|EMA/方法开发者|NAMs数据自愿提交试点|9月1日来源披露；未编造截止|动物试验替代方法监管沟通；保存正文不足|[EMA News RSS](https://www.ema.europa.eu/en/news/voluntary-data-submission-pilot-advance-innovative-alternatives-animal-testing)|查看原文/附件补充，当前不发布或忽略|FAIL|PASS|
|221|上海市科委及申报单位|探索者计划第二批七专题申报通知|8月28日披露；各专题期限需附件核对|含疾病药物/医疗装备方向，不借用其他专题资金|[上海市科学技术委员会](https://stcsm.sh.gov.cn/zwgk/kyjhxm/xmsb/20260828/14ffb521b3314d59b370e2087e73235e.html)|补充医药专题证据；保持不发布|FAIL|PASS|
|323|药明生物|2026H1业绩披露（标题），保存正文混导航|8月25日披露；H1为报告期，不是披露日|公司经营结果应核原文，不凭标题造金额|[WuXi Biologics](https://www.wuxibiologics.com/press-release/wuxi-biologics-reports-strong-profitable-growth-in-h1-2026)|补充可靠正文或忽略；保持不发布|FAIL|PASS|
|215|Roche/Genentech|美国制造扩建，约7.5亿美元投资和250岗位|8月20日披露；建设为计划，不是假称已完成|制造能力变化；不是已确认采购需求|[Roche Media Releases](https://www.roche.com/media/releases/med-cor-2026-08-20)|核对附件后再发布；当前门槛仍禁止发布|PARTIAL|PASS|
|333|Pharmaron/Biortus|签署收购协议，提升结构生物学服务能力|正文2025-10-28；自动披露时间未知，未填今天|历史并购事项，不等于当前可参与商机|[Pharmaron](https://www.pharmaron.com/about-us/latest-news/pharmaron-acquires-biortus)|补充真实日期/附件或忽略；保持不发布|PARTIAL|PASS|

所有10条来源URL与来源名称可确认，原文入口真实href正确；本轮不重新联网验证外站可达。未知披露日明确待核对，不默认今天；已知事件日/报告期不当成披露日。资金数额、监管阶段及多专题范围不跨项归因。

## Chromium与隔离操作

从工作台→情报→审核发布，再按类别列表点击核对并审核，逐条打开10份正文。未隐藏失败样本；6条原publishable=false保持禁用，4条原可发布不降门槛。10条均无横向溢出。
隔离库中#319忽略带原因，#345通过并发布形成产品#36；刷新及Web重启后保留；重复发布桥接仅1条。viewer发布和忽略均403；私有详情和证据API均404。Console/PageError/核心HTTP错误/Network Failure=0。最终#366规则修复后又用Chromium读取同一保存样本，地点断言通过。
测试脚本两次定位失败分别为跳转尚未完成和两个同名note输入；仅修测试等待目标标题与语义定位，没有提高超时或削弱断言。未运行全量pytest，历史失败只保留债务。

## Event #7只读决策

Event #7 / Profile #1：v05c_club_event_profiles.id=1、event_id=7、event_no=QBE-20260630-0001、draft/closed，创建2026-06-30T16:37:32。父events #7缺失。历史备份记载名称Q BAY，活动时间未记录；审计#44为2026-07-01T13:57:15 POST /manage/events/7/delete，success/303，删除理由未记录。

当前六类报名/参与/反馈/签到token/签到审计/关系候选均0；p4_domain_events.event_id=7亦0。活动列表及详情INNER JOIN父events，孤儿不可见；隔离GET /club/events和/api/v1/events均200，/club/events/1及/api/v1/events/7均预期404。新建活动以父ID和profile.event_id的最大值分配ID、父子同事务，未发现该新建路径会复用7。

但现行POST /api/v1/club/events/{club_event_id}/transition→ClubEventService.transition_event只查profile，不查events。profile #1当前draft，符合publish允许状态，继而可open；还会发出event.published领域事件。register也只检查profile和开放状态。该路径为真实注册、manage_club/membership.view_self受控API，而非死代码。

更重要：当前v05c_club_event_registrations的membership FK仍指向v04f_club_memberships_old，sqlite_master确认该表不存在；register在BEGIN前调用_allow_v05c_legacy_fk_compatibility，满足条件时执行PRAGMA foreign_keys=OFF。这是现存空表Schema风险，foreign_key_check只有1条不能证明它不存在。没有重做全库审计，没有新增异常记录。

EVENT_7_DECISION = FREEZE_BLOCKER。不能签署ACCEPT_AS_KNOWN_DEBT，因为活跃API仍可推进残留，不能保证不扩散。此结论依据只读代码分支、实际Schema和GET行为；本轮没有对Event执行POST，也没有将静态分析冒称已在正式库复现写入。

后续最小授权事项：针对这条活动写路径增加父对象存在性保护，并明确修复/封堵当前FK关闭兼容分支；隔离验证后重判冻结。不要求恢复或删除Event #7，不要求200表治理。数据删除/恢复仍需单独授权；本轮未改活动代码或正式库。

## 数据与版本

正式库只读；未跑正式Source/采集/加工，没有正式发布或审核决定变化。隔离副本操作不进入正式库。最终200表内容逐表SHA、Schema及DB SHA均与开始一致；integrity_check=ok。唯一FK集合仍(v05c_club_event_profiles,1,events,0)，不再清理GROUP-01，不重建Membership表。除本轮5个预期修改的既有dirty文件外，另80个原dirty文件字节指纹不变；新增/修改共12个本轮交付文件。清单、提交计划与当前git status的92项逐项一致；AST及git diff --check通过。
当前ACTIVE_RUNTIME_MAP的情报主链继续有效，已补充活动连接保护例外，不重做全项目审计。CURRENT_BASELINE及KNOWN_ISSUES已更新，旧PGF问题未冒称已验证通过。
WORKTREE_MANIFEST和COMMIT_PLAN逐文件列出92项；来源无UNKNOWN，候选不等于批准提交。历史备份只形成方案，32保留恢复、418待外置，实际删除/移动=0。
本轮产品改动仅v05g_processing模板、_review_facts模板、article_facts一条正则与6项测试；其余为指定基线/清单/结果文档。无commit、tag、Schema变更、新依赖或新业务模块。8775隔离实例已停止；closeout_02临时目录的10个本轮文件及目录已清理，临时账号随隔离库移除，浏览器上下文已关闭。未清理历史备份、R2种子或用户正式实例。正式Web未自动重启，人工查看新Python规则需按现有RUN方式正常重启；隔离验收已完成重启验证。

## 冻结判定

审核PASS、定向检查PASS、ChromiumPASS、dirty来源明确、数据保护成立；Event #7“不会继续影响活跃业务”的条件不成立，未解决P1=1，因此必须NO。
唯一下一步：用户授权最小活动写入口保护处理并隔离复核。解除阻断且人工确认后才按COMMIT_PLAN进行PC V1 Baseline Commit/Tag → API Freeze → 微信小程序V0.1。当前停止，不开发新的PC功能、不进入API或小程序。


后续时点：2026-09-17 CLOSEOUT-03已修复本记录识别的孤儿状态/报名写保护并移除请求关闭FK，正式报名表单表迁移通过；新确认参与表旧FK仍在单表授权之外，整体冻结暂NO。以[CLOSEOUT_03_RESULT](CLOSEOUT_03_RESULT.md)、CURRENT_BASELINE和KNOWN_ISSUES当前状态为准，不覆盖本文件历史证据。
