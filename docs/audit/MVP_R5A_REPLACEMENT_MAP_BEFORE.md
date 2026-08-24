# MVP-R5A Infrastructure Replacement Map（Before）

| Capability | Current Implementation | File | LOC | Current Caller | Replacement |
| --- | --- | --- | ---: | --- | --- |
| RSS / Atom | ElementTree手工识别channel/item/entry并遍历标签 | `app/services/collection_service.py::_parse_rss` | 24 | `process_job` feed分支 | feedparser集中适配，保留ExtractedPage业务映射 |
| HTML正文（Collection） | 手工删除DOM噪声、候选节点选择、短行去重 | `app/services/collection_service.py` 三个helper | 37 | `extract_html` | Trafilatura主抽取 + 极小BeautifulSoup纯文本fallback |
| HTML正文（URL） | 第二套DOM清洗和正文节点评分 | `app/web_extractor.py` 两个helper | 66 | `fetch_and_extract` | 与Collection共用同一Trafilatura基础helper |
| 标题去重相似度 | `difflib.SequenceMatcher.ratio()` | `app/services/fact_deduplication_service.py` | 2 | Fact冲突/去重 | RapidFuzz统一similarity helper，阈值语义不变 |
| Entity名称相似度 | 标准化/去后缀后直接调用两次SequenceMatcher | `app/v04e_entity_resolution.py::score_pair` | 32 | duplicate candidate scan | 保留业务规则和阈值，仅替换通用ratio计算 |
| Research事件标题相似度 | 直接调用SequenceMatcher | `app/services/research/fusion_service.py` | 1 call | `classify_event_relation` | 同一RapidFuzz helper |
| 正式定时调度 | APScheduler两个Cron job | `app/services/collection_scheduler.py` | 120 | app startup、Collection UI | 收敛为一个APScheduler collection cycle，同callable支持manual run |
| 重复Scheduler | 读取`scheduler_jobs`并自行判断due、创建task_queue任务 | `scripts/run_scheduler.py` | 47 | `start_scheduler_windows.bat` | 删除自研调度逻辑，CLI仅托管现有APScheduler |
| 专用Collection Worker | 单独参数/入口调用Collection `run_worker` | `scripts/run_collection_worker.py` | 46 | 专用Windows BAT、verify_all | 删除专用并行入口；manual和scheduled均调用Collection scheduler cycle |
| 统一Worker | `while`循环消费通用task_queue | `scripts/run_worker.py` | 63 | `start_worker_windows.bat` | 保留为非定时任务执行器，不再承担正式定时调度 |

## 调用关系判断

- 正式Web生命周期：`app/main.py` → `collection_scheduler.start_scheduler()` → APScheduler。
- 人工采集：Collection UI → `run_scheduler_once()`；当前实现与APScheduler job并非完全同一callable。
- Windows调度：`start_scheduler_windows.bat` → `scripts/run_scheduler.py`，当前仍走自研`scheduler_jobs`机制，且传入脚本不支持的`--sleep`参数。
- 专用Collection Worker与统一Worker并存；R5A只移除Collection专用重复入口，不删除仍执行其他任务类型的统一Worker。

静态搜索仅用于定位；上述结论已结合import、路由、BAT、README和测试调用关系核对。
