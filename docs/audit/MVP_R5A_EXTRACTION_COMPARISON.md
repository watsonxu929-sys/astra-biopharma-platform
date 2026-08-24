# MVP-R5A HTML正文抽取比较

日期：2026-08-24。比较只读使用正式库既有 `v04g_source_snapshots.raw_html`，没有把快照或抽取结果写回正式库。Old为快照中已保存的旧 `cleaned_text` 长度，New为同一Raw HTML在内存中经Trafilatura得到的长度；人工判定看正文语义、导航/Footer污染、重复、空正文和乱码，不以字符更多为优。

| Snapshot | 来源/页面 | Old chars | New chars | 人工判定 | 说明 |
| ---: | --- | ---: | ---: | --- | --- |
| 29 | EMA CHMP 2026-07会议摘要 | 12720 | 10832 | PASS | 长正文和药品表格语义保留；重复标签来自药品字段，不是导航。 |
| 27 | EMA领导团队任命 | 2074 | 1602 | PASS | 标题、任命正文和人物信息完整，无Footer。 |
| 26 | FDA Page Not Found | 568 | 395 | PASS | 忠实抽取错误页正文；页面质量由既有质量层判断，不伪造文章。 |
| 24 | FDA召回与安全警报 | 2530 | 2956 | PASS | 主说明和召回内容保留，无乱码。 |
| 22 | FDA Press Announcements | 1359 | 677 | PASS | 保留官方安全提示、页面标题和公告说明；未把整站导航作为正文。 |
| 20 | EMA执行主任议会演讲 | 10435 | 9566 | PASS | 演讲长正文完整，无明显重复。 |
| 19 | EMA/EISMEA合作新闻 | 3380 | 2411 | PASS | 合作内容和背景完整，无Footer。 |
| 18 | EMA CVMP 2026-07会议摘要 | 5104 | 4699 | PASS | 主要会议结论和药品信息保留。 |
| 9 | FDA Contact FDA | 1793 | 1679 | PASS | 联系渠道正文保留，未抽入全站菜单。 |
| 7 | EMA CVMP 2026-06会议摘要 | 5866 | 4973 | PASS | 主要会议结论完整，无乱码。 |

上述10个不同URL全部使用 `trafilatura` 主抽取，替换字符数均为0，空正文为0。Snapshot 29首次使用 `favor_precision + include_tables` 时只得到310字符，定向样本及时发现该退化；最终采用Trafilatura稳定默认正文策略后恢复为10832字符。

另有 `tests/test_mvp_r5a_oss_foundation.py` 的10个确定性HTML fixture，覆盖新闻、企业新闻、政府网站、普通资讯、复杂DOM、大量导航、中文、人物访谈、项目公告和园区动态。它们逐项验证正文存在、导航/Footer标记未进入正文、无乱码、无EXTRACTION_EMPTY，结果10/10 PASS。Fallback只剩Trafilatura空结果后的基础BeautifulSoup纯文本，不保留旧节点打分系统。
