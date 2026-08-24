# MVP-R5A OSS许可记录

记录日期：2026-08-24。版本为本轮验收环境实际安装版本，`requirements.txt`仅约束正式直接依赖的稳定主版本范围。

| Project | Version | Upstream | License | Commercial-use note | Project usage | Replacement scope |
| --- | ---: | --- | --- | --- | --- | --- |
| feedparser | 6.0.14 | https://github.com/kurtmckee/feedparser | BSD-2-Clause | 允许商业使用、修改和再分发；交付时保留版权及免责声明。 | Collection Service集中Feed adapter | RSS/Atom语法解析 |
| Trafilatura | 2.2.0 | https://github.com/adbar/trafilatura | Apache-2.0 | 允许商业使用；遵守版权、许可证、NOTICE及专利条款。2.x不是早期GPL版本。 | 共享HTML正文helper | HTML主正文抽取 |
| RapidFuzz | 3.14.5 | https://github.com/rapidfuzz/RapidFuzz | MIT | 允许商业使用、修改和再分发；保留版权与许可声明。 | 统一0..1 similarity helper | 通用字符串ratio计算 |
| APScheduler | 3.11.3 | https://github.com/agronholm/apscheduler | MIT | 允许商业使用、修改和再分发；保留版权与许可声明。 | 唯一正式定时调度底座 | Collection cycle定时注册 |

直接依赖约束：`feedparser>=6.0.14,<7.0`、`trafilatura>=2.2,<3.0`、`rapidfuzz>=3.14.5,<4.0`、既有 `apscheduler>=3.10,<4.0`。未复制任何上游LICENSE全文，本文件只作工程合规索引。
