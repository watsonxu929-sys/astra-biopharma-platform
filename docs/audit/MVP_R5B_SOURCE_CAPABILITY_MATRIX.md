# MVP-R5B 来源能力矩阵

记录日期：2026-08-24（Asia/Shanghai）

## 正式来源矩阵

| Source | Type | HTTP | Playwright | Trafilatura | Result | Problem |
| --- | --- | --- | --- | --- | --- | --- |
| 药明康德 | official_site | PASS | PASS | PASS | HTTP_SUFFICIENT | 正式health为历史paused，当前URL实测正常 |
| 鲸准 | rss（配置）/JS应用（实际） | SKIP | SKIP | N/A | ROBOTS_DENIED | robots明确拒绝；类型配置也不准确，本轮不改正式数据 |
| 36氪企服点评/融资平台 | webpage | INCOMPLETE（56字、无标题） | PASS 3/3（538–694字） | PASS | PLAYWRIGHT_REQUIRED | 页面自身固定console error；有界DOM等待后内容稳定 |
| EMA News RSS | rss | PASS | 不需要 | PASS | HTTP_SUFFICIENT | Feed正式路径由feedparser解析，详情由Trafilatura抽取 |
| FDA Press Announcements | list_page | PASS | PASS | PASS | HTTP_SUFFICIENT | 正式来源当前disabled/quarantined，R5B不改运营状态 |
| ClinicalTrials.gov Search | dynamic_page | FETCH_FAILED | PASS | PASS | PLAYWRIGHT_REQUIRED | HTTP受限，真实Chromium取得38651字 |

正式来源结论：HTTP足够3个、Playwright需要2个、robots拒绝1个；robots允许来源在Playwright后仍失败0个。

## 10个有效真实URL实测

| URL类别 | URL | HTTP结果 | Playwright结果 | 当前策略 |
| --- | --- | --- | --- | --- |
| 企业官网 | `https://prod-alb-officialsite.wuxiapptec.com/` | 200 / 1246字 | PASS | HTTP |
| 媒体JS页 | `https://pitchhub.36kr.com/` | 200 / 56字 / 无标题 | 3/3 PASS / 538–694字 | Playwright |
| 监管Feed | `https://www.ema.europa.eu/en/news.xml` | 200 / PASS | 不需要 | HTTP/feedparser |
| 监管详情 | `https://www.ema.europa.eu/en/news/new-leadership-team-appointments` | 200 / 1602字 | PASS | HTTP |
| 监管详情 | `https://www.ema.europa.eu/en/news/meeting-highlights-committee-medicinal-products-human-use-chmp-20-23-july-2026` | 正式HTTP采集PASS | PASS | HTTP |
| 监管列表 | `https://www.fda.gov/news-events/fda-newsroom/press-announcements` | 200 / 670字 | PASS | HTTP |
| 动态检索 | `https://clinicaltrials.gov/search?cond=biopharma` | FETCH_FAILED | 200 / 38651字 | Playwright |
| 企业新闻/Consent | `https://www.biontech.com/int/en/home/newsroom.html` | 200 / 1167字 | PASS | HTTP |
| 企业懒加载列表 | `https://www.astrazeneca.com/media-centre/press-releases.html` | FETCH_FAILED | 200 / 1381字 | Playwright |
| 企业新闻列表 | `https://www.roche.com/media/releases` | 200 / 1950字 | PASS | HTTP |

另对正式鲸准URL执行robots检查，结果denied，合规跳过，不计入10个实际抓取URL。选择阶段发现3个旧详情URL已返回真实404，已从能力样本排除，不把内容下线误判为采集引擎失败。

## 能力分层数字

- 不需要浏览器：7。
- HTTP + Trafilatura即可：7。
- 必须Playwright：3。
- Playwright后仍失败：0。
- 用户登录、验证码、付费墙、robots或访问控制绕过：0。

## 完整动态smoke

OS临时测试库对36Kr执行两次完整链：首轮 `SUCCESS/new=1/snapshot=1`，复跑 `DUPLICATE/unchanged=1/snapshot=1`；正式Intelligence 0、测试库integrity `ok`。临时库已删除，正式库未变。
