# P2.2 Playwright 适配器

依赖独立维护在 `requirements-playwright.txt`，延迟导入；未安装时主应用可正常启动，动态任务返回 `parser_or_collector_unavailable`。只有 `collection_mode=playwright` 才调用浏览器，默认仍是HTTP。

适配器支持超时、关键选择器、最终HTML、页面标题、诊断截图路径和最多20条网络错误摘要。浏览器在 `finally` 中关闭；不登录、不处理验证码、不无限滚动。截图只作本地诊断，不提交Git。

真实试点使用 Playwright 1.61 / Chromium 149，ClinicalTrials.gov 动态搜索成功形成 Snapshot 和 RawIntelligence。
