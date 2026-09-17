# ASTRA-R2：栏目采集到文章审核（2026-09-16）

状态：**code_complete / manual_acceptance_pending**。真实性、业务价值及正式发布由用户确认；不宣称全站覆盖或长期稳定。

## 使用入口与变化
- 情报 → 采集与数据源：保留现有 Source、运行与原始情报页面；栏目支持有限分页、持久化详情链接、失败重试及详情正文抓取。
- 情报 → 审核发布（具有 review_data 权限）：查看全文、编辑补充、发布或忽略。文章审核与实体匹配分离，发布复用 Canonical Writer。
- 发布后回到情报首页与详情，显示真实中英文标题、正文、来源与原始时间；缺失日期不伪造。未知主体不自动建立档案。
- 相同 URL、稳定订阅标识或正文抑制重复；下架、归档和人工忽略不会因采集恢复。URL 去重身份与实际栏目请求分开，保留请求尾斜杠及业务参数。
- 跟进模型仍要求绑定 Opportunity；没有该情报的既有 Opportunity 时明确提示限制，**不再为了记录跟进自动创建虚假商机**。

## 小样本实际产出
以下为正式库最终成功运行；首次三个 HTML 运行因配置去除末尾斜杠超时，真实失败记录保留。修复配置保存后重试成功。

|Source / 栏目|入口读取|发现链接|取得正文|新增/变更|重复|规则相关并进入审核|未进入原因|
|---|---|---:|---:|---:|---:|---:|---|
|23 上海科委：项目申报（两页）|成功|38|20|20/0|0|7|13篇被现有领域/内容质量规则过滤；剩余链接受20篇预算限制|
|21 上海药监局：药品/器械注册证公告|成功|20|5|5/0|0|5|其余链接保存在现有发现表，受5篇预算限制|
|24 上海经信委：公示公告|成功|10|10|10/0|0|1|9篇被领域/内容质量规则过滤|
|4 EMA News RSS|成功|4|4|1/3|0|4|无；3篇属于已有 URL 正文变化|
|11 Roche Media Releases RSS|成功|4|4|4/0|0|4|无|
|10 BioNTech 新闻栏目（仅隔离试跑）|浏览器加载完成，但未发现有效文章链接|0|0|0/0|0|0|column_has_no_article_links；官方 IR 备用入口请求超时；未绕访问限制|

具体栏目 URL：
- https://stcsm.sh.gov.cn/zwgk/kyjhxm/xmsb/
- https://yjj.sh.gov.cn/ypylqxcpzczxxgg/
- https://sheitc.sh.gov.cn/gg/
- https://www.ema.europa.eu/en/news.xml
- https://www.roche.com/med_news_xml.xml
- https://www.biontech.com/us/en/home/mediaroom/news.html （缺口）

“规则相关”不等于人工有效率。正式生成21条待审核文章，未自动发布任何文章。经信委混合领域公告仍需人工判断，不把建设、融资或合作措辞当真实需求/商机。关键附件未解析的条目要求人工核查，不宣称已读附件。

## 技术验证及数据边界
- 隔离真实试跑覆盖 RSS、HTML 栏目、两页分页、Chromium 动态页面。EMA/Roche 各重复运行一次，均4条重复、0新增加工任务。
- 9项离线主线检查通过；网络调用已拦截，仅显式隔离测试库。不运行全量 pytest。Python AST 与 git diff --check 通过。
- Chromium 151.0.7922.34，1440×900：从正常菜单进入文章审核，人工动作脚本发布隔离候选205，情报列表/详情35可读，刷新及服务重启后保留。Console/Page Error、HTTP异常、Network Failure、页面横向溢出均0。Viewer 编辑/审核/发布分别403。
- 正式业务发布仍为0；原情报33继续 withdrawn。未新增用户、主体、资源、机会或跟进。浏览器独立测试库（包含临时账号及测试发布）、日志、临时脚本及截图已移除；8772无监听。隔离采集种子 trial.db 留在忽略目录用于重现离线检查，不纳入Git；正式数据和安全备份未删除。
- 正式一致性备份：`data/backups/ASTRA_R2_PRE_COLLECTION_20260916.db`；重试前另有 `ASTRA_R2_PRE_COLUMN_RETRY_20260916.db`。
- 与首次备份逐表比较：185张表内容完全相同；仅14张现有来源、采集、加工、候选证据/计数/锁表改变。Source实际变更仅4/11/21/23/24，Source3和10未动，Source数量141不变。
- Collection 647→690；Snapshot 76→119；Processing Job 57→78。新增实体匹配均候选，不是正式主体。
- Schema完全相同；integrity_check=ok；完整FK集合仍为 `(v05c_club_event_profiles, 1, events, 0)`，未处理Event7。
- 正式DB SHA256：前 `c22e61b5ee08450ad9c0f9cb040b305e51da933e5a70c896ae7aec859fb1af67`；后 `e9652796cf9220bf5761efcc0b9440df9ed592e89febf789238e31c19f558410`。变化来自上述授权真实运行。

## 本轮文件与保留状态
生产服务：`collection_service.py`、`collectors/playwright_adapter.py`、`processing/content_quality_service.py`、`processing/processing_job_service.py`、`intelligence_review_service.py`、`intelligence_product_service.py`、`golden_loop_service.py`、`navigation_service.py`（均在 app/services）。

入口与模板：`app/platform/capability_registry.py`、`app/v05g_processing.py`、`app/v05f_collection.py`；`app/templates/v05g_processing.html`、`v05f_collection.html`、`base.html`、`platform/intelligence_detail.html`。

测试：`tests/test_astra_r2_mainline.py`；简短结果：本文件。新增业务表/Model/依赖/Writer均0。

开始时55个未提交文件已保全于 `data/backups/ASTRA_R2_WORKSPACE_SAFETY_20260916_132055.zip`；其中49个未涉及文件保持逐字节一致，6个交叉文件仅增量修改。未reset/restore/clean/stage/commit。

Branch：`release/mvp-rc1.2`；HEAD：`3a491a5b61632b9531f08f5453e66978444398e5`；Working tree：dirty（原G/H/R1与本轮修改保留）。

人工下一步：重启现有Web，在“情报 → 审核发布”核对真实文章价值、来源和缺项，选择发布/补充/忽略；发布后从情报首页阅读。没有Opportunity时独立FollowUp属于明确模型缺口，不属于已交付能力。不进入R3。
