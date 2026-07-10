# v0.5J 专题研究、企业对比、招商研判与中文化治理

## 范围

v0.5J 在现有主体、事件、关系、信号、报告、关注清单、招商线索和 Q-BAY 规则基础上，新增产业专题、企业对比、赛道分析和招商研判入口。业务数据仍保存英文机器字段，用户界面通过集中映射显示中文。

## 中文化治理

集中映射位于 `app/i18n/`：

- `zh_cn.py` 保存中文标签表。
- `helpers.py` 提供 `translate_status`、`translate_type`、`translate_role`、`translate_permission`、`translate_error`、`translate_field`、`translate_enum`。
- API 保留 `status`、`type`、`grade` 等稳定英文机器值，同时增加 `status_label`、`type_label`、`grade_label` 等中文展示字段。

当前不建设英文界面切换，也不翻译企业正式英文名、产品名、药物名、API 路径、URL、邮箱、Q-BAY、CMC、BD、API、RSS、JSON、CSV、PDF、Word、Excel 等白名单内容。

## 专题研究

新增表：

- `research_topics`
- `research_topic_subjects`
- `research_snapshots`

专题类型支持赛道、区域、企业群、技术路线、投融资、招商专题和自定义专题。主体可人工加入，服务层也预留规则/导入/推荐来源。刷新专题时只保存统计快照和引用，不复制主体、事件、信号或关系原始数据。

专题驾驶舱聚合企业、人物、项目、事件、信号、融资、合作、临床、招聘、风险、招商机会、数据完整度和来源覆盖度。时间线只使用已确认数据；关系网络复用现有 `relations`，并限制节点数量。

## 企业对比

企业对比支持 2 到 8 家企业，不允许重复。对比维度包括基础信息、资本、技术产品、团队、业务发展、风险与机会。缺失数据展示“无公开信息”“数据不足”“待核实”，不把未披露解释为“没有”。

评分仅提供独立维度：信息完整度、近期活跃度、资本活跃度、技术进展度、招商匹配度、关系可达性、风险关注度，不生成企业总分。

## 赛道分析

赛道分析基于企业标签、事件和信号聚合。支持近 7 天、近 30 天、近 90 天、近一年和自定义窗口。趋势判断必须显示当前窗口、对比窗口、样本数量、变化值、变化比例、数据完整性、主要来源和结论置信度。样本不足时显示“样本量不足，暂不形成趋势判断”。

## 招商研判

新增表 `investment_assessments`。研判结果区分已确认事实、系统规则判断、招商建议和待核实事项。评级支持：

- `A`：重点优先
- `B`：建议跟进
- `C`：观察培育
- `D`：暂不优先
- `R`：本地资源协同型
- `UNVERIFIED`：身份或数据不足

研判遵循 Q-BAY 招商规则：本地资源协同不错误归为 D，数据不足不强行评级。评级默认是候选，人工批准后才允许转为既有招商线索，不自动创建行动任务，不覆盖人工跟进记录。

## 页面入口

新增入口均位于“产业分析”二级导航：

- `/research`
- `/research/topics`
- `/research/topics/new`
- `/research/companies/compare`
- `/research/tracks`
- `/research/investment`

未新增顶部一级菜单。

## API

新增专题 API、企业对比 API、赛道 API 和招商研判 API，详见 `docs/API_V1_GUIDE.md`。写操作继续复用现有权限和审计中间件。

## 验证

专项验证：

```powershell
.venv\Scripts\python.exe scripts\verify_v05j.py
.venv\Scripts\python.exe scripts\check_user_visible_english.py
```

全量验证：

```powershell
.venv\Scripts\python.exe scripts\verify_all.py
```

