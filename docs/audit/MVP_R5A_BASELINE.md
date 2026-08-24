# MVP-R5A 基线

记录日期：2026-08-24（Asia/Shanghai）

## 正式现场

| 项目 | 值 |
| --- | --- |
| Project path | `E:\\Codex项目设计\\招商一体化平台系统\\biopharma-intelligence-mvp-rc1` |
| Branch | `release/mvp-rc1.2` |
| HEAD | `d8335658a7ed800779202495ceb371407a49ed58` |
| Git status | clean |
| Python | `3.14.2` |
| Formal DB | `E:\\Codex项目设计\\招商一体化平台系统\\biopharma-intelligence-mvp-rc1\\data\\app.db` |
| DB SHA256 | `26328F6DED572A3942424D54CF4A67C5A298F5413177B21FD96086D3BCCE4404` |
| integrity_check | `ok` |

数据库SHA256通过允许其他本项目进程同时只读/写入的共享文件句柄计算；基线期间未停止既存Web进程，也未写正式业务数据。

## 正式直接依赖（Before）

`requirements.txt` 当前包含 Pillow、APScheduler、BeautifulSoup、FastAPI、HTTPX、Jinja2、OpenPyXL、pydantic-settings、python-docx、python-multipart、SQLAlchemy、Uvicorn、xlrd。APScheduler已安装为 `3.11.3`；feedparser、Trafilatura、RapidFuzz尚未安装。

## 正式业务数据

| Table | Rows |
| --- | ---: |
| v06_intelligence_items | 25 |
| people | 44 |
| organizations | 24 |
| v06_market_resources | 29 |
| p4_resource_match_candidates | 0 |
| v06_opportunities | 11 |
| p3_canonical_relationships | 25 |

## 采集基线

| 项目 | 值 |
| --- | ---: |
| Collection相关Service文件 | 4 |
| Collection相关Python LOC | 1423 |
| 正式Source总数 | 6 |
| 正式启用Source | 5 |
| v05f_collection_items | 391 |

Service统计口径：`app/services/collection_service.py`、`app/services/collection_scheduler.py`、`app/services/collectors/*.py`。

## 当前基础实现位置

- Feed：`app/services/collection_service.py::_parse_rss`，24 LOC，直接使用 `xml.etree.ElementTree` 遍历RSS/Atom标签。
- HTML正文（采集链）：同文件 `_clean_soup`、`_best_node`、`_text_from_node`，合计37 LOC；`extract_html`承担业务字段映射。
- HTML正文（URL提取）：`app/web_extractor.py::_clean_html`、`_best_content_node`，合计66 LOC，与采集链重复。
- Fuzzy：`app/services/fact_deduplication_service.py`、`app/v04e_entity_resolution.py`、`app/services/research/fusion_service.py`直接调用 `difflib.SequenceMatcher`。
- Scheduler：`app/services/collection_scheduler.py`已有APScheduler；`scripts/run_scheduler.py`仍有47 LOC的数据库轮询式自研调度；另有46 LOC专用Collection Worker CLI及63 LOC统一Worker循环。

R5A只替换这些通用基础能力；URL安全校验、HTTP/Playwright Fetcher、业务字段映射、状态机、去重、Canonical读写均不属于删除范围。
