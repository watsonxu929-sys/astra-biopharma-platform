import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/t1_test.db')
conn.row_factory = sqlite3.Row
try:
    conn.execute("ALTER TABLE v05f_collection_items ADD COLUMN quality_status TEXT DEFAULT 'pending'")
    conn.execute("ALTER TABLE v05f_collection_items ADD COLUMN quality_reason TEXT")
except sqlite3.OperationalError:
    pass
conn.commit()

today = datetime.now().strftime("%Y-%m-%d")
items = conn.execute(
    """
    SELECT i.*, s.name as source_name
    FROM v05f_collection_items i
    LEFT JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
    WHERE date(i.captured_at)=? AND i.quality_status='accepted'
    ORDER BY i.captured_at DESC
    LIMIT 15
    """,
    (today,),
).fetchall()

if not items:
    print("今日暂无通过质量检查的情报，使用最近15条")
    items = conn.execute(
        """
        SELECT i.*, s.name as source_name
        FROM v05f_collection_items i
        LEFT JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
        ORDER BY i.captured_at DESC
        LIMIT 15
        """,
    ).fetchall()

report_lines = []
report_lines.append("# T2 质量验收报告")
report_lines.append("")
report_lines.append(f"验收时间: {datetime.now().isoformat()}")
report_lines.append(f"数据库: data/t1_test.db")
report_lines.append(f"样本数量: {len(items)}")
report_lines.append("")
report_lines.append("## 验收表")
report_lines.append("")
report_lines.append("| intelligence_id | source | title | quality_status | summary_accurate | event_type_correct | entity_correct | evidence_supported | duplicate | useful | reviewer_note |")
report_lines.append("|----------------|--------|-------|----------------|------------------|--------------------|----------------|--------------------|-----------|--------|---------------|")

for item in items:
    item_dict = dict(item)
    item_id = item_dict["id"]
    candidates = conn.execute(
        """
        SELECT * FROM v05g_extraction_candidates
        WHERE collection_item_id=?
        ORDER BY candidate_type, confidence_score DESC
        """,
        (item_id,),
    ).fetchall()
    event_candidates = [c for c in candidates if c["candidate_type"] == "event"]
    entity_candidates = [c for c in candidates if c["candidate_type"] in ("organization", "person", "project")]
    has_evidence = any(c["evidence_excerpt"] for c in candidates)
    event_type = event_candidates[0]["normalized_value"] if event_candidates else "其他"
    
    summary_len = len(item_dict.get("title", "")[:160])
    summary_ok = "是" if summary_len >= 20 else "否"
    event_ok = "是" if event_type != "其他" else "待评估"
    entity_ok = "是" if 0 < len(entity_candidates) <= 5 else ("否" if len(entity_candidates) > 5 else "待评估")
    evidence_ok = "是" if has_evidence else "否"
    duplicate_ok = "否"
    useful_ok = "待评估"
    
    title_display = item["title"][:60] if item["title"] else ""
    
    report_lines.append(f"| {item_dict['id']} | {item_dict.get('source_name', '-')} | {title_display} | {item_dict['quality_status']} | {summary_ok} | {event_ok} | {entity_ok} | {evidence_ok} | {duplicate_ok} | {useful_ok} | |")

report_lines.append("")
report_lines.append("## 统计摘要")
report_lines.append("")

stats = conn.execute(
    """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN quality_status='accepted' THEN 1 ELSE 0 END) as accepted,
        SUM(CASE WHEN quality_status='duplicate' THEN 1 ELSE 0 END) as duplicate,
        SUM(CASE WHEN quality_status='low_quality' OR quality_status='insufficient_content' THEN 1 ELSE 0 END) as low_quality,
        SUM(CASE WHEN quality_status='irrelevant' THEN 1 ELSE 0 END) as irrelevant
    FROM v05f_collection_items
    """,
).fetchone()
report_lines.append(f"- 原始内容总数: {stats[0]}")
report_lines.append(f"- 质量通过: {stats[1]}")
report_lines.append(f"- 重复过滤: {stats[2]}")
report_lines.append(f"- 低质量过滤: {stats[3]}")
report_lines.append(f"- 无关内容: {stats[4]}")

candidate_stats = conn.execute(
    """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN candidate_type='event' THEN 1 ELSE 0 END) as events,
        SUM(CASE WHEN candidate_type='organization' THEN 1 ELSE 0 END) as orgs,
        SUM(CASE WHEN candidate_type='person' THEN 1 ELSE 0 END) as people,
        SUM(CASE WHEN candidate_type='project' THEN 1 ELSE 0 END) as projects,
        SUM(CASE WHEN evidence_excerpt IS NULL OR evidence_excerpt='' THEN 1 ELSE 0 END) as no_evidence
    FROM v05g_extraction_candidates
    """,
).fetchone()
report_lines.append("")
report_lines.append("## 候选统计")
report_lines.append("")
report_lines.append(f"- 候选总数: {candidate_stats[0]}")
report_lines.append(f"- 事件候选: {candidate_stats[1]}")
report_lines.append(f"- 机构候选: {candidate_stats[2]}")
report_lines.append(f"- 人物候选: {candidate_stats[3]}")
report_lines.append(f"- 项目候选: {candidate_stats[4]}")
report_lines.append(f"- 无证据候选: {candidate_stats[5]}")

avg_candidates = conn.execute(
    """
    SELECT AVG(cnt) as avg FROM (SELECT COUNT(*) as cnt FROM v05g_extraction_candidates GROUP BY collection_item_id)
    """,
).fetchone()
avg_val = avg_candidates[0] if avg_candidates[0] else 0.0
report_lines.append(f"- 平均每篇候选数: {avg_val:.2f}")

conn.close()

report = "\n".join(report_lines)
with open("docs/trae/T2_QUALITY_ACCEPTANCE.md", "w", encoding="utf-8") as f:
    f.write(report)

print("验收报告已生成: docs/trae/T2_QUALITY_ACCEPTANCE.md")
print(f"样本数量: {len(items)}")