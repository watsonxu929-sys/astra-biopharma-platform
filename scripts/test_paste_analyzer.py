import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analyzer import analyze_text

sample = """
2026年6月26日，上海示例生物科技有限公司宣布完成5000万元A轮融资。
本轮融资将用于临床前研究、研发团队扩充和实验室平台建设。
公司专注于ADC创新药研发，目前核心管线处于临床前阶段。
"""

result = analyze_text(sample, "行业媒体")

checks = [
    ("event type", result.event_type == "融资与资本"),
    ("date", result.event_date == "2026-06-26"),
    ("amount", "5000万元" in result.amount),
    ("ADC tag", "ADC" in result.industry_tags),
    ("funding need", "资金" in result.potential_needs),
    ("space need", "空间" in result.potential_needs),
]

failed = 0
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    failed += 0 if ok else 1

print("RESULT:", result.to_dict())
if failed:
    raise SystemExit(1)
print("ALL ANALYZER CHECKS PASSED")
