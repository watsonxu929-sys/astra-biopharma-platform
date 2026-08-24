# MVP-R6 数据质量报告

## KPI

| 指标 | 结果 | 口径 |
| --- | ---: | --- |
| Collection Success Rate | 7/7 = 100% | 运行 110～116；success 或 unchanged，failed content 0 |
| Extraction Success Rate | 16/16 = 100% | 11 success + 5 needs_review；技术处理失败 0 |
| Duplicate Rate | 6/32 = 18.75% | duplicate 1 + unchanged 5；changed 4 不计为重复 |
| Intelligence Publish Rate | 5/27 = 18.52% | R6 人工审核事件候选中形成 5 条唯一正式情报 |
| 七周期直接发布率 | 1/32 = 3.13% | 七周期新记录中只有 Q-BAY 项目达到正式发布标准 |
| Subject Candidate Coverage | 1/5 = 20% | 5 条新正式情报中，1 条产生至少一个合理的现有主体候选 |
| Confirmed Subject Coverage | 1/5 = 20% | Q-BAY 候选经人工确认写入既有 link 表 |
| Intelligence → Resource | 1 | Q-BAY 正式供给资源 |
| Intelligence → Opportunity | 0 | 没有真实、明确的合作对手方，不制造机会 |

## 七周期质量分布

| 质量状态 | 数量 | 比例 |
| --- | ---: | ---: |
| accepted | 17 | 53.13% |
| low_quality | 11 | 34.38% |
| irrelevant | 3 | 9.38% |
| access_denied | 1 | 3.13% |

- 空正文/抓取失败：0；7 个周期 `failed_content_count` 均为 0。
- Bad title / 通用页：发现 Contact、Careers、History、Strategy、Leadership、Stories、Mediaroom、Press Releases、Research & Innovation、ClinicalTrials.gov 等栏目标题；已在现有质量服务中加入统一确定性门，不增加站点专用框架。
- 实体噪声：拒绝句子型标题、过长标题及明显拼接字符串，避免把说明句自动当作企业。
- 正式发布：5 条均有来源、URL、证据、发布时间/采集时间、可信度和确定性重要性说明；无通用栏目页被正式发布。

## 人工审核样本

本轮人工审核 27 个真实事件候选：

- 6 个 approved：5 个唯一正式情报 + 1 个同源同标题重复证据。
- 2 个 rejected duplicate：已有正式主情报，不重复发布。
- 19 个 rejected noise/misclassification：栏目页、通用页或规则误分类。

候选有效或可作为重复证据的比例为 6/27（22.22%）；噪声比例为 19/27（70.37%）。该结果不美化，直接用于停用 FDA/ClinicalTrials/AstraZeneca 当前入口并收紧通用质量门。

主体候选准确性样本为 1/1：Source Registry 中 Q-BAY 的正式机构绑定产生置信度高的候选，用户确认后写入 `core_intelligence_subject_links`。EMA 情报没有对应的既有正式主体，因此保持不关联；不为覆盖率乱建人物或企业。

## 去重验收

- URL/规范 URL、GUID、Content Hash 和标题相似继续使用现有 Collection 去重规则；R2～R6 定向测试通过。
- EMA CHMP 同源同标题候选 91 发布时命中正式情报 29，只追加候选/证据与 `exact_duplicate_evidence_linked` 审计，不新建第 2 条 Intelligence。
- “同一事件不同来源”没有强制删除，也没有为多来源新建 Schema；本轮没有足够可靠的跨来源样本进入正式库。

## 失败来源

药明康德（连续失败）、鲸准（robots denied）、FDA 当前入口（泛列表噪声）、ClinicalTrials 当前入口（通用搜索页）、AstraZeneca 当前入口（访问/同意页）均已停用并保留历史证据。
