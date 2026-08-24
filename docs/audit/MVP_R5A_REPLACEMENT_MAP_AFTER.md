# MVP-R5A Infrastructure Replacement Map（After）

| Capability | Before | After | Old LOC Removed | New LOC | Result |
| --- | --- | --- | ---: | ---: | --- |
| RSS / Atom | ElementTree手工Feed解析 | 单一 `_parse_rss` adapter调用feedparser，保留ExtractedPage字段映射 | 24 | 24 | PASS |
| HTML正文 | Collection 37 LOC、URL提取66 LOC、HtmlParser 5 LOC三套规则 | 单一17 LOC Trafilatura helper + 极小纯文本fallback | 108 | 17 | PASS |
| Fuzzy | 3文件直接import SequenceMatcher、4个ratio调用 | 单一3 LOC RapidFuzz 0..1 helper；业务标准化、阈值和决策不变 | 7 | 3 | PASS |
| Scheduler | APScheduler双job + 47 LOC自研scheduler + 46 LOC专用Worker + 29 LOC专用BAT | APScheduler单一 `collection_cycle`；manual、timed和due-only task均调用同一callable | 122 | 67 | PASS |

## 最终调用关系

- Timed：APScheduler → `run_collection_cycle` → 既有 `schedule_due_collection_jobs` / `run_collection_worker_with_cascade`。
- Manual：`run_scheduler_once` → 同一个 `run_collection_cycle`。
- Unified task queue的due-only任务也转调同一个cycle，不再复制schedule+worker编排；统一Worker只作为非定时任务执行器。
- Windows Scheduler BAT只托管 `scripts/run_scheduler.py`；CLI不再读 `scheduler_jobs`、不自行计算due、不创建第二套定时任务。
- Playwright仍负责动态网页渲染；Trafilatura只接收渲染后的Raw HTML。

## 删除与规模

删除了ElementTree Feed遍历、两套DOM清洗/节点评分、所有生产SequenceMatcher调用、自研scheduler_jobs轮询脚本逻辑、专用Collection Worker CLI和专用BAT。正式 `app/**/*.py + scripts/**/*.py`：68837 LOC → 68756 LOC，净减少81 LOC；未新增业务表、Model、Service、版本目录或Canonical写路径。
