# MVP-R6 Source Registry 真实清单

审计日期：2026-08-24。可信度沿用 `source_credibility`：A=5（监管机构、政府、企业或项目官方），B=4（成熟产业媒体/数据库）。R6 最终保留 15 个来源而非追求 20～30 个数字目标，原因是质量优先，未验证来源只进入 CANDIDATE。

| Source | Category | URL | Collection Method | Frequency | Last Success | Quality | Keep |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 药明康德 | 企业动态 | https://prod-alb-officialsite.wuxiapptec.com/ | HTTP | 日频 | 2026-07-01 16:32 | A；连续失败 3 次 | DISABLED |
| 鲸准 | 投融资 | https://cloud.jingdata.com/#/home | HTTP | 人工 | 无 | B；robots denied | DISABLED |
| 36克 | 投融资/企业动态 | https://pitchhub.36kr.com/ | HTTP | 人工 | 2026-07-02 15:19 | B；当前 degraded | ACTIVE（人工） |
| EMA News RSS | 监管/研发/获批 | https://www.ema.europa.eu/en/news.xml | Feed + HTTP | 日频 | 2026-08-24 15:17 | A；稳定、有明确正文 | ACTIVE |
| FDA Press Announcements | 监管/获批 | https://www.fda.gov/news-events/fda-newsroom/press-announcements | HTTP | 日频 | 2026-08-24 15:17 | A；入口发现食品/召回泛列表噪声 | DISABLED |
| ClinicalTrials.gov Search | 临床研发 | https://clinicaltrials.gov/search?cond=biopharma | Playwright | 日频 | 2026-08-24 15:17 | A；动态抓取成功，但入口只形成通用检索/术语页 | DISABLED |
| BioNTech Newsroom | 企业动态/研发 | https://www.biontech.com/int/en/home/newsroom.html | HTTP | 日频 | 2026-08-24 15:18 | A；已加入通用栏目页质量门 | ACTIVE |
| Roche Media Releases | 企业动态/研发 | https://www.roche.com/media/releases | HTTP | 日频 | 2026-08-24 15:18 | A；已加入通用栏目页质量门 | ACTIVE |
| AstraZeneca Press Releases | 企业动态/研发 | https://www.astrazeneca.com/media-centre/press-releases.html | Playwright | 日频 | 2026-08-24 15:18 | A；动态渲染成功但取得访问/同意页 | DISABLED |
| Q-BAY公开项目动态 | Q-BAY/产业资源 | https://www.qianrenwuye.com/index.php?a=index&aid=193&c=View&m=home | HTTP | 周频 | 2026-08-24 15:18 | A；具体公开项目页，可关联正式机构 | ACTIVE |
| CDE公开信息 | 监管/研发 | https://www.cde.org.cn/ | HTTP | 人工 | 无 | A；待选择具体公告入口 | CANDIDATE |
| NMPA政务服务公告 | 监管政策 | https://zwfw.nmpa.gov.cn/ | HTTP | 人工 | 无 | A；待验证稳定公告入口 | CANDIDATE |
| 上海生物医药外资项目政策 | 产业政策 | https://www.shanghai.gov.cn/gwk/search/content/781af56e96a74f579986bea8cd51a8f8 | HTTP | 人工 | 无 | A；具体政策页，因来源禁用状态人工运行 117 被安全跳过 | CANDIDATE |
| Pfizer Press Release Archive | 企业动态/研发 | https://www.pfizer.com/news/press-release/press-release-archive | HTTP | 人工 | 无 | A；待验证列表到正文发现质量 | CANDIDATE |
| Novartis Media Releases | 企业动态/研发 | https://www.novartis.com/news/media-releases | HTTP | 人工 | 无 | A；待验证列表到正文发现质量 | CANDIDATE |

## 频率与准入结论

- 高频来源：本轮没有设置；当前数据量与运营能力不需要一天多次。
- 日频：EMA、BioNTech、Roche。APScheduler 继续调用现有 Collection callable。
- 周频：Q-BAY 公开项目动态。
- 人工：36克及 5 个 CANDIDATE；未经人工验证不得进入自动周期。
- 连续失败、robots denied、严重噪声或访问页来源直接 DISABLED，不继续堆叠站点特例。
