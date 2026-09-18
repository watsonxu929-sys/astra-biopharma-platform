# 当前唯一可信基线（优先阅读）

## 当前：2026-09-17 / ASTRA-K1

PC V1基线已提交：`c21cb5d8c9fdbd30e6c44a54d662c7f0820e50cd`，注释Tag `pc-v1-baseline`准确指向该提交；人工验收仍待用户确认，不表示公开上线批准。
K1状态：CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING；新增代码未提交、未打Tag。正式Web仍使用本唯一目录，正式自动采集保持已停止，未改变34个既有启用来源或各自频率。
014加法迁移已应用，203表；原业务列内容不变。3份官方公开资料形成6个资料版本、269条待审结构候选，正式Knowledge仍34条，自动发布=NO。原Event #7唯一FK例外不变，integrity_check=ok。新增内容不是已经人工确认的政策结论。
直接检查37项通过（K1 11、R3 15、活动主链7、既有知识/培训4）；真实Chromium资料提交、定时拆解、合并、草稿/明确发布、版本更新、笔记保留、权限和暂停重启已验证。未跑全量pytest，不宣称历史测试债务已复测。正式实例仍沿用开发免登录设置：K1私人材料/知识在该模式下拒绝上传、读取与列表暴露；内部资料须先启用真实登录认证，本轮未改全站认证配置。
迁移恢复点、真实样本、限制与人工入口见 [ASTRA_K1_RESULT](audit/ASTRA_K1_RESULT.md)。本轮不提交K1、不移动基线Tag、不启动后续阶段。

## PC V1代码基线授权 / 2026-09-17

ASTRA-K1明确授权按现有98项清单提交PC V1代码基线，建议Tag pc-v1-baseline；此授权不等于全部功能人工验收完成或公开上线批准。人工验收仍待确认，活动链自动浏览器验收结果与Event #7历史例外保持下文记录。
对应SQLite Backup API恢复点：data/backups/PC_V1_BASELINE_20260917_151702.db；SHA256 7cea3e74d280b6a10299f3f1a8207da8c8259bf6f5ec66bca9d263329756e99e。同名JSON保留实际Schema、user_version和迁移记录，不进入Git。K1新增修改与此代码基线分开，不自动提交或移动Tag。

## 历史时点：2026-09-17 / ASTRA-CLOSEOUT-03 CONTINUE

CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING；TECHNICAL_FREEZE_BLOCKER_CLEARED=YES（本轮完整活动链）；PC_V1_BASELINE_COMMITTED=NO。
- 正常有效普通会员与独立管理员，在同一活动连续完成报名→批准→参与→签到→查看，真实Chromium刷新/重启通过；18项定向检查通过。正常业务链FK OFF=0，孤儿保护、权限、重复动作、事务失败与迁移回滚均有直接隔离证据；未跑全量pytest/正式采集。
- 本轮唯一结构变更：空参与表会员FK改为正式会员表；原正确报名/签到表跳过。200表业务内容/行数不变，Event #7数据不变；精确异常仍为(v05c_club_event_profiles,1,events,0)，integrity_check=ok。
- 正式库当前SHA256：6ed8cbe98be93d4b793326fe05703e25ee8af727a5b8009a6730d0f25452c417；新PRE/POST及保全ZIP见[CLOSEOUT_03_RESULT](audit/CLOSEOUT_03_RESULT.md)。正式8000/reload恢复，Scheduler/Worker关闭；18个本轮临时文件与空目录已清理，8776已停止。
- Branch release/mvp-rc1.2；HEAD 3a491a5b61632b9531f08f5453e66978444398e5；98项未暂存候选，已核实K12解除；8个P2/2个P3保留。等待人工确认PC V1提交/Tag，不自动执行下一阶段。

## 原CLOSEOUT-03历史时点（不覆盖上述当前结论）

CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING（本轮报名与孤儿保护）；PC_V1_FREEZE_READY=NO。
- 原孤儿活动活跃写风险已封堵，正常有效会员在FK=ON下报名/查询通过；正式报名FK已指向v04f_club_memberships(id)。
- 唯一历史FK异常仍为(v05c_club_event_profiles,1,events,0)，200表业务内容均不变，integrity_check=ok。正式DB现SHA256 23aff4ebe3a17ce327c04118b7a262a831b0df6b97fba2eba43f8594c639374e；恢复点与结构核对以[CLOSEOUT_03_RESULT](audit/CLOSEOUT_03_RESULT.md)为准，旧hash仅作历史时点。
- 新确认K12：参与表旧会员FK不在单表授权范围，报名批准/签到返回明确维护503而不关闭FK；因此不宣布整体冻结阻断清零。
- 11项直接隔离检查通过，未跑全量/采集/真实浏览器写入；正式Web按原8000/reload恢复，等待人工操作。Branch/HEAD不变；95项未暂存候选，禁止自动commit/tag。
- 8项P2和2项P3未处理；PRE/POST与工作区快照保留。更新仅本轮指定文件，详见结果及提交清单。

## CLOSEOUT-02历史时点（下文不覆盖上述当前结论）

2026-09-16 / ASTRA-CLOSEOUT-02。任务收口CODE_COMPLETE / MANUAL_ACCEPTANCE_PENDING；PC_V1_FREEZE_READY=NO（Event活跃写入口P1）。这是未提交候选工作区，不是已冻结版本。

- 唯一工程：E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1；正常开发用本目录Git分支；不依赖旧rescue或C:\tmp作为正式工作树。
- Branch release/mvp-rc1.2；HEAD 3a491a5b61632b9531f08f5453e66978444398e5；本轮开始85项dirty（含CLOSEOUT-01），原G/H/R1/R2/R3有效修改保留，无提交。
- Python .venv/Scripts/python.exe 3.14.2；启动run_windows.bat；正式Web默认关闭内嵌scheduler/worker，独立运行脚本存在但本轮不启动采集。
- 唯一正式DB data/app.db，200表/0view/384index，27918336字节；SHA256 c96c47012013a25135ea316d54bf78f3da090a6fb4e4e503bfd500bb9ec60c9d；integrity_check=ok。历史FK唯一标识(v05c_club_event_profiles,1,events,0)，Event #7不自动修；不能仅凭异常数判非阻断，具体活跃API/FK关闭风险见KNOWN_ISSUES K01。
- 主链唯一地图：[ACTIVE_RUNTIME_MAP](audit/ACTIVE_RUNTIME_MAP.md)。Collection成功→自动Processing→证据facts/quality→人工审核→Canonical发布→Unified阅读。旧文件名前缀不能视为死代码。
- R3 view/reading/reading_use/facts.view分工已经重新验证；现有24定向检查通过。本轮另修私有情报详情/证据可被viewer访问的P1，4个单元边界检查加隔离API/Chromium通过。
- 真实数据：Source142、Collection728、Processing100、Candidate389、正式Intelligence记录2；审核页当前显示42待审核。38条R3真实采集和22任务没有重跑、删除、重建；不自动发布，不替代人工审核。
- 正式库只读；测试使用data/acceptance/astra_r2/trial.db种子或明确隔离复制库。测试前设置APP_DB_PATH与DATABASE_URL、关闭scheduler/worker，严禁导入默认正式库测试。
- 删除仅pyc/pytest缓存；备份、工作区快照、原证据KEEP。空间/逐库/dirty清单见[PROJECT_BASELINE_INVENTORY](audit/PROJECT_BASELINE_INVENTORY.md)。
- [DEFERRED_BACKLOG](audit/DEFERRED_BACKLOG.md)是当前延后清单；[MINIPROGRAM_READINESS](audit/MINIPROGRAM_READINESS.md)明确认证与API契约缺口。10栏目不等于全业务覆盖；基金、人物、采购、科研/IP仍未补。
- 28个不同定向用例通过，未跑全量pytest，不声明历史失败集合已复测。Chromium151、1440×900真实菜单阅读/审核检查错误0；仍需用户判断事实提炼与审核可读性。
- 正式收尾结果见[CLOSEOUT_01_RESULT](audit/CLOSEOUT_01_RESULT.md)。本轮不继续R4/新来源/AI/小程序开发。

本轮审核10条真实样本业务判定PASS（事实不足可明确忽略/补充，不等同允许全部发布）；34个定向用例通过；Chromium发布/忽略、刷新重启、viewer403、private404均通过。修复审核信息重复/误导占位和Avenue误命中venue导致会议地点串联两项P1。正式库保持只读。

当前权威问题以[KNOWN_ISSUES](KNOWN_ISSUES.md)为准；[CLOSEOUT_02_RESULT](audit/CLOSEOUT_02_RESULT.md)、[WORKTREE_MANIFEST](audit/WORKTREE_MANIFEST.md)、[COMMIT_PLAN](audit/COMMIT_PLAN.md)给出精确候选。历史CLOSEOUT-01是时点记录，不覆盖本次新发现。

唯一阻断：活动写路径父记录保护与FK关闭兼容分支，需要下一次明确授权的最小处理。解除并复核后，等待人工确认 → PC V1 Baseline Commit/Tag → API Freeze → 微信小程序V0.1。现在不commit/tag、不进入API开发，不增加PC功能。
