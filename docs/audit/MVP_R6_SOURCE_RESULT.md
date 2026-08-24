# MVP-R6 来源最终状态

最终总数：15；ACTIVE 5，DISABLED 5，CANDIDATE 5。没有删除来源或历史运行。

## ACTIVE

| Source | 理由 | 频率 |
| --- | --- | --- |
| EMA News RSS | 官方 Feed，具体事件正文稳定，产生 4 条高价值正式情报 | 日频 |
| BioNTech Newsroom | 企业官方，HTTP 正常；通用栏目页由统一质量门拦截 | 日频 |
| Roche Media Releases | 企业官方，HTTP 正常；通用栏目页由统一质量门拦截 | 日频 |
| Q-BAY公开项目动态 | 真实运营生态，已形成 Intelligence → Organization → Resource | 周频 |
| 36克 | 成熟产业媒体，保留人工触发；健康度 degraded，不自动提频 | 人工 |

## DISABLED

| Source | 理由 |
| --- | --- |
| 药明康德 | 连续失败 3 次且已自动暂停；保留历史，不继续维护当前入口 |
| 鲸准 | robots denied；不得绕过站点规则 |
| FDA Press Announcements | 当前宽入口发现食品事件、Contact、召回列表等大量无关/泛页面 |
| ClinicalTrials.gov Search | Playwright 成功，但当前 URL 只产生搜索根页和术语内容，不是具体试验事件 |
| AstraZeneca Press Releases | Playwright 动态渲染成功，但质量门取得访问/同意类页面，无可发布正文 |

## CANDIDATE

| Source | 后续准入条件 |
| --- | --- |
| CDE公开信息 | 找到稳定、具体的公告/受理/审评入口并完成受控周期 |
| NMPA政务服务公告 | 证明可稳定取得具体公告正文且无登录/验证码依赖 |
| 上海生物医药外资项目政策 | 以具体政策页人工验证，确认更新频率后再启用 |
| Pfizer Press Release Archive | 验证列表发现到具体正文的质量与重复率 |
| Novartis Media Releases | 验证列表发现到具体正文的质量与重复率 |

## 动态来源结论

ClinicalTrials.gov 与 AstraZeneca 的 Playwright 渲染均执行成功，证明 R5B 动态采集能力仍可用；两者因业务内容质量而停用，不是浏览器技术失败。未引入 Crawl4AI 或第二套采集链。
