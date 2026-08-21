# MVP-R1 正式产品表面收敛最终验收报告

验收日期：2026-08-21（Asia/Shanghai）

## 结论

`PARTIAL`

当前状态：`partial / manual_browser_acceptance_pending`

阻断类型：`TOOLING_BLOCKED`。真实浏览器内核在加载任何产品页面前即因宿主 Windows ACL 失败退出：`windows sandbox failed: helper_unknown_error: apply deny-read ACLs`。该结果既不等于产品失败，也不等于浏览器验收通过。依照任务规则，本轮未继续重试浏览器、未修改业务代码处理工具问题、未提交 Git。

## 基线与范围

| 项目 | 结果 |
|---|---|
| 项目目录 | `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1` |
| 分支 | `release/mvp-rc1.2` |
| 基线 HEAD | `b79efabcec4e5a58d4490f076efb8ceb042a7cbd` |
| 本轮范围 | R1产品表面收敛、兼容重定向、测试隔离、验收与审计 |
| 新模型 / 新Service / 新数据库表 / 新版本目录 | 0 / 0 / 0 / 0 |
| 重复Registry / 第二套路由体系 | 0 / 0 |
| Git提交 | 未提交；因浏览器验收未完成，不满足PASS提交条件 |

## 产品表面 Before / After

| 项目 | Before | After |
|---|---|---|
| 一级导航 | 工作台 / 产业关系 / 情报中心 / 资源市场 / 业务协同 / Q-BAY | 工作台 / 情报 / 关系 / 资源 / 协作 |
| 一级导航数量 | 6 | 5 |
| viewer可见Capability | 41 | 15 |
| operator可见Capability | 56 | 15 |
| reviewer可见Capability | 未单独记录 | 15 |
| admin可见Capability | 62 | 62 |
| Q-BAY定位 | 一级导航 | `运营场景：Q-BAY` |

当前15项普通用户可见能力为：工作台、待办、最近跟进、情报、情报流、关系、人物、资源、需求、供给、协作、任务、Q-BAY、Q-BAY会员、Q-BAY活动。

### Admin Only 与 Frozen

- Admin可见能力总数为62；其中47项不进入普通用户R1产品表面，可视为本轮的Admin Only/内部保留集合。
- Frozen能力为上述47项普通用户不可见能力：代码和历史数据均保留，不删除、不迁移、不恢复到普通用户导航。
- 47项内部状态构成为41项 `active`、6项 `beta`；`Frozen` 是R1产品表面处置结论，不伪造或改写原Registry内部状态。
- 从普通产品表面移除/冻结的范围包括：版本化入口、帮助入口、订阅、专题研究、情报运营后台、候选与推荐实验、关系推荐、模拟匹配、系统治理与其他Legacy入口。
- 未新建第二个Capability Registry；15项白名单直接位于既有 `app/platform/capability_registry.py`。

## FastAPI路由统计口径

- 当前完整加载 `app.main:app` 后实际展开：704个Route上下文、647个唯一path。
- 修改前：700个Route上下文、643个唯一path；该值由当前值减去Git diff中唯一新增的四个兼容别名路由可靠反推。
- 四个新增path：`/dashboard`、`/resources/demand`、`/resources/supply`、`/resources/matching`。
- `len(app.routes)=77` 只表示顶层对象（含lazy router），不作为FastAPI真实路由数。

## Legacy Redirect

隔离候选实例通过真实监听端口实测：

| 入口 | HTTP | Location | 结论 |
|---|---:|---|---|
| `/dashboard` | 303 | `/platform` | 正确 |
| `/member` | 303 | `/club` | 正确 |
| `/resources/demand` | 303 | `/resources?direction=demand` | 正确 |
| `/resources/supply` | 303 | `/resources?direction=supply` | 正确 |
| `/resources/matching` | 303 | `/resources?message=matching_pending` | 不伪装成熟匹配产品，正确回到资源市场提示 |

## 自动测试隔离与数据保护

- `tests/conftest.py` 不再复制正式库；模板固定为专用测试库 `data/t1_test.db`。
- 每个测试将模板以SQLite只读连接复制到 pytest 的Windows OS临时目录，随后仅在该临时副本上运行既有006–011迁移和写入。
- 正式库绝对路径固定为 `E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`，fixture显式禁止它成为模板或写目标。
- R1表面、RC1.2定向、正式库保护测试合计：`12 passed`。

### 正式数据库前后对比

| 项目 | 测试前 | 测试后 |
|---|---|---|
| SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` |
| `integrity_check` | `ok` | `ok` |
| `people` | 44 | 44 |
| `organizations` | 24 | 24 |
| `v06_intelligence_items` | 25 | 25 |
| `v06_market_resources` | 20 | 20 |
| `v06_opportunities` | 11 | 11 |
| `v06_follow_ups` | 4 | 4 |
| `p4_resource_match_candidates` | 0 | 0 |
| `p3_canonical_relationships` | 0 | 0 |

结论：正式数据库文件哈希、完整性与全部八张核心表行数前后完全一致；没有用正式业务数据通过测试。

## 浏览器真实验收结果

| 项目 | 结果 |
|---|---|
| 目标方式 | 真实运行实例 + Chrome/Playwright浏览器控制 |
| 候选地址 | `http://127.0.0.1:8012` |
| 候选数据库 | Windows OS临时验收数据库，不是正式库 |
| 浏览器版本 | `unavailable`；内核在建立会话前退出 |
| 页面真实渲染 | 未执行 |
| Browser Console Error | `UNKNOWN / unavailable`，不得填写0 |
| 浏览器Network 404/500 | `UNKNOWN / unavailable`，不得填写0 |
| 截图 | 未生成；首页、情报、关系、资源、协作、Q-BAY、Console、404/500证据均待人工浏览器验收 |
| 状态 | `TOOLING_BLOCKED` / `manual_browser_acceptance_pending` |

### 应用自身启动与HTTP可达性证明（不替代浏览器证据）

候选Web已从当前仓库启动，`/login` 返回200；临时operator登录后最终到达 `/platform` 并返回200。通过真实监听端口检查以下15个目标，全部返回200：

`/platform`、`/intelligence`、`/intelligence/1`、`/network/people`、`/network/organizations`、`/resources`、`/resources?direction=demand`、`/resources?direction=supply`、`/resources/3`、`/opportunities`、`/opportunities/2`、`/club`、`/club/members`、`/club/events`、`/search?q=生物医药`。

该结果证明应用正常启动且目标路由不存在HTTP 404/500，但不能证明HTML/CSS/JS真实渲染、Console为0、视觉无溢出或交互可用。

## 15分钟内人工浏览器验收步骤

候选地址：`http://127.0.0.1:8012/login`。临时账号只存在于OS临时验收库。

1. 用临时operator登录，打开工作台；确认一级导航严格为“工作台 / 情报 / 关系 / 资源 / 协作”，Q-BAY卡片显示“运营场景：Q-BAY”。在1366×768和较宽桌面各检查一次横向溢出。记录：`[ ] PASS  [ ] FAIL`。
2. 打开情报列表和任一情报详情；确认标题、当前状态、下一步提示正常且没有工程术语。保存“情报”截图。记录：`[ ] PASS  [ ] FAIL`。
3. 打开关系、人物、企业页面；确认导航高亮、标题与内容正常。保存“关系”截图。记录：`[ ] PASS  [ ] FAIL`。
4. 打开资源列表，分别点击需求/供给筛选，再打开一项Resource详情；访问 `/resources/matching` 应回到资源市场并显示尚未正式运营提示。保存“资源”截图。记录：`[ ] PASS  [ ] FAIL`。
5. 打开协作、Opportunity列表和详情；确认导航高亮与状态文字正常。保存“协作”截图。记录：`[ ] PASS  [ ] FAIL`。
6. 打开Q-BAY首页、会员、活动和全局搜索；确认Q-BAY作为运营场景呈现，无一级导航跳动。保存“Q-BAY场景”截图。记录：`[ ] PASS  [ ] FAIL`。
7. 访问 `/dashboard`、`/member`、`/resources/demand`、`/resources/supply` 验证重定向；在DevTools Console确认0 Error，Network筛选4xx/5xx确认正式可见链接0个404、0个500；全程确认无 `v04/v05/v06/P2/P3/P4/P5`、Golden Loop、Collection Pipeline、Processing、Candidate、Recommendation、AI实验、Research实验等用户可见工程术语。保存Console与Network截图。记录：`[ ] PASS  [ ] FAIL`。

## 修改结构与LOC

用户提供的“+844 / -0”不是当前Git工作树的实际统计。按 `git diff --numstat` 加未跟踪R1文档/测试文件逐行计数，最终为：`+387 / -110`。

| 类别 | +LOC | -LOC | 内容 |
|---|---:|---:|---|
| 正式产品代码 | 66 | 77 | 既有Jinja产品表面文案、卡片、入口显示与布局条件 |
| redirect / compatibility | 23 | 0 | 五个Legacy行为中的四个新增别名路由及一个既有 `/member` 行为替换 |
| capability / navigation | 24 | 10 | 既有Registry中的R1白名单及既有导航过滤 |
| tests | 108 | 23 | R1表面断言、RC1.2文案更新、测试库隔离、正式库保护 |
| audit / docs | 166 | 0 | 基线与本报告 |
| 其他 | 0 | 0 | 无 |

结构审计结论：新增运行时代码仅进入既有 `capability_registry.py`、`navigation_service.py` 和既有路由/模板；没有新业务抽象、重复Service、重复Registry或第二套路由体系，无需回退产品收敛修改。

## 修改文件列表

- `app/main.py`
- `app/platform/capability_registry.py`
- `app/routes_platform.py`
- `app/services/navigation_service.py`
- `app/templates/base.html`
- `app/templates/platform/base.html`
- `app/templates/platform/home.html`
- `app/templates/platform/intelligence.html`
- `app/templates/platform/intelligence_detail.html`
- `app/templates/platform/network.html`
- `app/templates/platform/opportunities.html`
- `app/templates/platform/resource_detail.html`
- `app/templates/platform/resources.html`
- `app/templates/v04f_club.html`
- `app/v05d_member_portal.py`
- `tests/conftest.py`
- `tests/test_mvp_rc1_2_product_acceptance.py`
- `tests/test_mvp_r1_product_surface.py`
- `tests/test_real_database_protection.py`
- `docs/audit/MVP_R1_BASELINE.md`
- `docs/audit/MVP_R1_PRODUCT_SURFACE_RESULT.md`

## 已知遗留问题与验收判定

1. 浏览器宿主通道未建立，因此没有真实渲染截图、Console和Network证据。
2. 候选实例和两个临时账号为人工验收保留在OS临时验收库；正式数据库无账号或数据残留。
3. 在人工浏览器验收完成前，不得提交Git、不得进入下一阶段。

R1代码表面、测试隔离、数据保护、路由可达性和报告均已完成；真实浏览器验收条件未满足。因此不满足R1全部验收条件，最终只能为：`PARTIAL`。
