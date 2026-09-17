# ASTRA-R3 收尾结果

状态：code_complete / manual_acceptance_pending。等待用户人工查看，不进入R4，不提交Git。

## 本次两处最小修复
- `app/routes_platform.py`：`intelligence_center` 的用途筛选参数 `view` 被循环中的阅读结果字典覆盖，非空列表向模板传入字典，触发 `read_views.get(view, ...)` 的 unhashable dict 500。仅将循环局部变量改名为 `reading`；筛选参数、查询、可见性及权限不变。
- `app/services/processing/content_quality_service.py`：旧 `reading_use` 是宽泛阅读用途，R3误将五类审核视图标签写入该字段，导致常规批件样本预期“行业观察”、实际“待核对”。恢复既有用途契约；审核分流仍使用 `facts.view/view_label`，缺日期仍待核对，不默认今天或高价值。未改断言、skip或xfail。

## 最小检查
- 修改前单独复现原失败用例，修改后通过；现有24项定向检查全部通过（R3事实13、R2主线9、R3运行边界2）。仅已有隔离种子、网络拦截；未运行全量pytest。
- Chromium 151.0.7922.34：从菜单进入情报，非空列表显示保存样本的真实标题、摘要和“待核对”时效；资本用途筛选保留该条目，叠加监管类别得到明确空结果，清除类别后条目恢复；详情原文链接及事实区可见。下架的情报33不在列表中。审核入口显示实际仍待审样本及审核动作。
- Console/Page Error、HTTP错误、Network Failure、外部请求均0；本次没有发布文章或重新采集。审核检查先误选已在隔离库发布的融资样本，后改为读取真实待审条目，没有恢复审核决定或改产品逻辑。
- 停止隔离Web后一次即时数据库读取出现I/O错误；随后独立只读连接核验两个隔离库 integrity_check=ok，文章逐行一致。未修改数据库访问层。两库已按授权清理。
- 两处Python AST检查和git diff --check通过。其余73个既有dirty文件保持收尾前字节指纹不变；原G/H、R1、R2、R3修改保留。

## 正式数据与清理
- 本次重跑正式采集：NO；正式写入、自动发布、Schema修改：0。
- 收尾前后200张表内容及Schema指纹相同，采集记录728、加工任务100不变；既有R3新增38条采集记录、22个加工任务及证据完整保留。
- 正式DB前后SHA256均为 `b90aa1b84bcccf264c5f3ac55e51a7ac4fe72a6fb58ce11a7f5329734421d689`；integrity_check=ok；完整FK集合仍为 `(v05c_club_event_profiles, 1, events, 0)`，未处理Event #7。
- 8773隔离实例已停止，`data/acceptance/astra_r3/` 的18个明确临时文件已清理，目录无文件残留。隔离账号随库移除；正式库、R2种子、正式一致性备份和工作区安全快照未删除。
- 5份一次性脚本及1张临时截图在删除副本前已逐文件验证归档：`data/backups/ASTRA_R3_CLOSEOUT_MATERIALS_20260916.zip`，SHA256 `eafb254fd78557f1692a8a834a025ce1a668bc51e7eb12c57e1de0f0c7a38a71`。未归档凭据、测试库和日志；未删除共享浏览器运行时。

## 保留的限制与Git
- 既有10个接通栏目不代表全业务覆盖；基金、人物、采购、科研/IP仍有缺口，本次不补来源、不联网补样本。
- 本记录是原R3结果文件未落盘后的唯一简短补记，不是新报告体系；未宣称人工价值验收通过。
- Branch：`release/mvp-rc1.2`；HEAD：`3a491a5b61632b9531f08f5453e66978444398e5`；工作区dirty、未暂存/提交。此次仅两处产品源码修复与本记录，停止等待人工查看。
