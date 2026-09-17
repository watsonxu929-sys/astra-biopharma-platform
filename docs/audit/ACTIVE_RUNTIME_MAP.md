# 唯一有效运行地图

CURRENT_SOURCE_OF_TRUTH = 当前实际工作区 + data/app.db；不是旧报告、文件名版本号或其他目录。
运行入口 run_windows.bat → scripts/windows/start_web_windows.bat → run_web_launcher.py → app.main:app。
Web脚本明确 SCHEDULER_ENABLED=false、WORKER_ENABLED=false；不把Web可打开说成后台持续采集已启动。独立调度入口 scripts/run_scheduler.py，旧验证脚本也引用flow，但本轮不执行它们。
应用真实展开 _iter_routes_with_context(app.routes)：802个注册route（含静态Mount），805个HTTP method绑定；不是顶层lazy-router数量，亦非唯一URL数。未删除任何旧路由。审计范围不是全802端点的安全认证。

## 主链

1. 情报→采集与数据源；v05f_collection页面GET/POST及API collection入口；手工run和scheduler都复用collection_service。scheduler每15分钟调用run_collection_cycle→schedule_due_collection_jobs（来源小时/日/周频率）→collection worker cascade。来源v04g_monitoring_sources，运行v04g_monitoring_runs，快照v04g_source_snapshots，原文v05f_collection_items，发现/去重/锁使用现有v05f表。
2. process_collection_job_with_automation→advance_processing_after_collection→create_processing_jobs_for_collection_run→run_processing_worker_once→processing_job_service。v05g_processing_jobs/blocks/extraction_candidates保存任务与候选；article_facts提炼证据和时间，content_quality_service计算可发布门槛。无自动正式发布。
3. /processing/review-queue→list_review_queue仅article_review未形成正式产品的pending/needs_review/approved→v05g_processing.html。详情/edit/review/publish调用IntelligenceReviewService与IntelligenceProductService；审核/发布权限、忽略不可自动复活及有证据编辑受测试约束。
4. publish_candidate经校验进入CanonicalWriter→v06_intelligence_items；p2_intelligence_product_candidates/evidence桥接原候选和快照。这些p2命名是活动证据路径，不是可删Legacy。
5. published→UnifiedIntelligenceService.list→product_facts/matches_reading→routes_platform.intelligence_center→platform/intelligence.html。详情及API共同复用Unified.detail；本轮补齐与列表相同的visibility保护。已下架/归档仍遵循既有历史与管理员生命周期视图，不删除历史。
6. 模板表单负责采集/审核操作；没有第二个JS发布实现。PC收藏/关注AJAX在routes_platform的/api/v1/favorites/toggle、follows/toggle，使用现有服务；不把它们误当作完整小程序契约。

## 模块分类（限本次13个主链目标）

|模块|分类|调用/证据|
|---|---|---|
|app/routes_platform.py|ACTIVE|main→platform_router；intelligence_center→Unified.list→golden.reading_view→platform/intelligence.html；详情→Unified.detail|
|app/v05f_collection.py|ACTIVE|main注册；collection页面表单→create_job/process_collection_job_with_automation；v05f_collection.html|
|app/services/collection_service.py|ACTIVE_SHARED|Web/API/flow调用；来源、运行、快照、原始采集写入；HTTP/Playwright适配已有|
|app/services/collection_scheduler.py|ACTIVE|main startup与scripts/run_scheduler.py调用；15分钟tick；按来源频率判断due|
|app/services/intelligence_flow_service.py|ACTIVE_SHARED|scheduler/collection routes/worker；Collection成功→advance_processing_after_collection→processing worker|
|app/services/processing/processing_job_service.py|ACTIVE_SHARED|flow与v05g路由；加工任务、article_review候选；list_review_queue动态评估并筛选facts.view/category|
|app/services/processing/article_facts.py|ACTIVE_SHARED|quality与reading共用；确定性事实、日期证据、用途视图、有效期；非LLM|
|app/services/processing/content_quality_service.py|ACTIVE_SHARED|加工/审核/发布调用article_review_quality；reading_use保持宽泛用途，facts.view独立|
|app/v05g_processing.py|ACTIVE|main注册；review-queue/candidate edit/review/publish；v05g_processing.html和_article_facts.html|
|app/services/intelligence_review_service.py|ACTIVE_SHARED|v05g/API及R2测试；审核权限、状态与决策写回现有候选|
|app/services/intelligence_product_service.py|ACTIVE_SHARED|v05g发布/生命周期/APItrace；CanonicalWriter发布，候选和证据桥接|
|app/services/unified_intelligence_service.py|ACTIVE_SHARED|PC和/api/v1/intelligence共同读取v06；published及visibility过滤；不是第二写入系统|
|app/v04c_review.py|ACTIVE_SHARED|main仍注册且广泛被服务导入；db_connection统一路径、FK=ON并回读确认；不是死代码|

ACTIVE + ACTIVE_SHARED = 13；DEAD=0（没有满足8项删除证明的模块）。其他模块不自动判死；未逐项审计者UNKNOWN。publish_from_raw保留为COMPATIBILITY_ONLY拒绝入口，返回409要求候选审核；它不证明整个Unified模块废弃。历史迁移和验证脚本有CLI/测试/恢复依赖，按DEPRECATED_BUT_REFERENCED或UNKNOWN保留。
数据库：app.settings解析DATABASE_URL/APP_DB_PATH；app.database SQLAlchemy connect启用FK；v04c_review.db_connection显式启用并确认FK。共享sqlite与ORM均指向配置解析路径。独立测试同时覆盖两个环境变量，禁止隐式正式回退。

## R3复核

STATUS = VERIFIED。view仍是查询字符串；循环reading仅存golden.reading_view结果；reading_use保持业务优先处理/行业观察的原契约；审核facts.view与阅读matches_reading有明确独立参数，不用缺失日期冒充今天。
24个不同既有用例全部通过；另4个可见性用例通过。日期/旧新闻/多期限/无日期/行业用途/审核与阅读共享规则均有离线检查。实际发现式加载额外重复R2九项，因此37次执行、28个不同测试，全部成功；非全量pytest。

## 实际运行证据与边界

隔离库来自当前正式库只读一致性复制，8774临时Web，Chromium 151.0.7922.34，1440×900。从/platform正常菜单进入情报，随后核对全部、资本、无匹配、详情、审核队列。实际文章“药品再注册批件领取通知（2026-14）”及审核队列42条可见；资本视图在当前数据为空，不制造样本。
5个检查页面均有真实内容/明确空态；Console/PageError/HTTP错误/network failure=0，横向溢出0；正式采集重跑NO。检查结束停止8774实例，保留用户正式Web。
API当前身份测试：列表/详情/证据/企业人物目录/搜索/client bootstrap=200；page=0为422；viewer加工写入403。私有详情/证据/HTML由原200改为404；恢复隔离样本原visibility后公开读为200。fixture的结果JSON复用URL键记录最后公开200，不把它误读成私有保护失败，私有断言在恢复前执行。

## 审核可读性：不扩大UI修改

发生什么：标题+summary；谁：facts.fields的可核实主体，缺失仍待核对；时间：publication候选与业务期限/新鲜度；为何值得收：facts.reason与质量gaps；来源：source_name、原文URL、可展开正文；下一步：确认发布、编辑补充、带原因忽略。
六项有现有承载，不代表每篇机器提炼都有业务价值。重复摘要/泛化占位、英文原文、长期展示忽略输入框影响阅读，列P2；“待审核文章”命名P3。当前没有独立清晰的“退回待核”按钮，需求待决策P2，不新建审核流程。不把Console=0等同人工可用性已认可。


## CLOSEOUT-02边界补充

情报主链和路由数量未改。审核展示增加_review_facts宏去重/不足提示；article_facts仅修正event地点正则词边界。不要将上文连接入口默认FK=ON解读为所有服务永不关闭FK：ClubEventService.register有现存关闭FK兼容分支，且当前条件成立，详见KNOWN_ISSUES K01。Event状态API遗漏父存在性检查，PC冻结暂NO。


## CLOSEOUT-03原活动边界（历史时点）

上述CLOSEOUT-02活动风险已部分替代：父活动保护同事务生效，报名表正式会员FK已修复，正常请求关闭FK兼容已删除。正常报名通过；活动参与表仍指向不存在的旧会员表，本轮未授权改它，批准/签到明确维护503。K01活跃孤儿风险封堵，K12冻结阻断保留；不影响既有情报主链地图。

## 当前CONTINUE活动边界

本轮按活动链授权修正空参与表会员FK。Web/API→同一ClubEventService→events/Profile、registration、participation、checkin tokens/audit、领域事件/操作审计；只有参与表需修，其他正确表不重建。业务事务FK ON；批准/签到身份、归属、状态及幂等保持一致，孤儿不产生成功副作用。正常UI完整链、刷新/重启和18项隔离检查通过，K12已解除；我的报名从当前身份读取真实参与状态，批量签到不吞错误。详情、恢复点与边界见CLOSEOUT_03_RESULT。未改变上述情报主链；未开展全系统连接审计。
