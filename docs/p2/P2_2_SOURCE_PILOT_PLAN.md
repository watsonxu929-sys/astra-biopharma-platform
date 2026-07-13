# P2.2 真实来源受控试点方案

试点批次 `P22-20260711-CODEX`，配置位于 `config/p2_2_source_pilot.json`。声明内容上限19，运行硬上限30；同源串行、间隔可配置、最多两次重试，遵守 robots，不登录、不绕验证码。

| 来源 | 机构 | URL | 类型/主题 | 采集方式 | 动态/附件 | 更新频率/可信度 | 预期字段 | 失败降级 | 上限 |
|---|---|---|---|---|---|---|---|---|---:|
| FDA Press Announcements | FDA | `https://www.fda.gov/news-events/fda-newsroom/press-announcements` | 静态/监管与产品 | HTTP | 否/否 | 持续/5 | 标题、日期、正文、链接 | 保留失败原因，人工复核 | 3 |
| EMA News | EMA | `https://www.ema.europa.eu/en/news?page=1` | 静态/欧洲监管 | HTTP | 否/否 | 持续/5 | 标题、日期、正文、链接 | 首轮旧URL 404；修正后成功 | 3 |
| BIO Press Releases | BIO | `https://www.bio.org/press-releases` | 静态/行业组织 | HTTP | 否/否 | 不定期/4 | 标题、日期、正文、机构 | 首轮单数URL 404；修正后成功 | 3 |
| EMA News RSS | EMA | `https://www.ema.europa.eu/en/news.xml` | RSS/监管新闻 | RSS+有限详情 | 否/否 | 持续/5 | 条目、详情链接、日期、正文 | 详情失败保留feed正文及关联 | 5 |
| ClinicalTrials.gov Search | NLM | `https://clinicaltrials.gov/search?cond=biopharma` | 动态/临床试验 | Playwright | 是/否 | 持续/5 | 最终HTML、标题、正文 | 未安装明确 unavailable，不回退伪页面 | 3 |
| 2025 New Drug Therapy Approvals | FDA | `https://www.fda.gov/media/190705/download?attachment=` | PDF/年度审批 | HTTP+Docling | 否/是 | 年度/5 | 文件、哈希、页码、章节、表格 | 超限拒绝；扫描件标记OCR required | 1 |
| NME/New Biologic Approvals Compilation | FDA | `https://www.fda.gov/media/177921/download?attachment=` | XLSX/历史审批 | HTTP+Docling | 否/是 | 更新/5 | 文件、哈希、工作表表格 | 结构失败进入人工复核 | 1 |

所有结果进入既有 `CollectionJob → EvidenceSnapshot → RawIntelligence → FactCandidate` 链。采集器不得写 `IntelligenceProduct`。
