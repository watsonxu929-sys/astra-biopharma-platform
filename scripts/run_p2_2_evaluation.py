from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai import OpenAIProvider, RuleProvider
from app.services.ai_budget import AIPilotBudget
from app.services.evaluation_service import evaluate_records


def _prediction(sample: dict, result, latency_ms: int, estimated_cost: float = 0.0) -> dict:
    organizations = [
        item.get("label") or item.get("name") for item in result.entities
        if str(item.get("type") or "").lower() in {"organization", "company", "agency"}
    ]
    people = [
        item.get("label") or item.get("name") for item in result.entities
        if str(item.get("type") or "").lower() == "person"
    ]
    return {
        "sample_id": sample["sample_id"], "event_type": result.event_classification,
        "organizations": [item for item in organizations if item], "people": [item for item in people if item],
        "products": [], "indications": [], "targets": [], "regions": [], "dates": [],
        "amounts": [], "stages": [],
        "candidates": [item.__dict__ for item in result.candidates],
        "latency_ms": {"ai": latency_ms}, "estimated_cost_usd": estimated_cost,
    }


def run(gold_path: Path, *, allow_ai: bool, ai_limit: int, max_cost_usd: float) -> dict:
    gold = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rule_predictions = []
    for sample in gold:
        started = time.perf_counter()
        result = RuleProvider().analyze(sample["text"], title=sample["sample_id"], source_url=sample["source_url"])
        rule_predictions.append(_prediction(sample, result, round((time.perf_counter() - started) * 1000)))
    output = {
        "gold_sample_count": len(gold),
        "rule": {"status": "completed", "metrics": evaluate_records(gold, rule_predictions)},
        "ai": {"status": "not_run", "reason": "AI execution not explicitly enabled or API key unavailable"},
        "hybrid": {"status": "not_run", "reason": "AI result unavailable"},
        "actual_ai_calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0,
    }
    provider = OpenAIProvider()
    if not allow_ai or not provider.available:
        return output
    budget = AIPilotBudget(max_calls=min(max(0, ai_limit), 20), max_cost_usd=max_cost_usd)
    ai_predictions = []
    hybrid_predictions = []
    total_tokens = 0
    for sample, rule_prediction in zip(gold[: min(ai_limit, 20)], rule_predictions):
        budget.reserve("openai")
        started = time.perf_counter()
        result = provider.analyze(sample["text"], title=sample["sample_id"], source_url=sample["source_url"])
        latency = round((time.perf_counter() - started) * 1000)
        cost = budget.record_usage(
            result.usage,
            input_cost_per_million=float(os.getenv("OPENAI_INPUT_COST_PER_MILLION", "0") or 0),
            output_cost_per_million=float(os.getenv("OPENAI_OUTPUT_COST_PER_MILLION", "0") or 0),
        )
        total_tokens += int(result.usage.get("total_tokens") or 0)
        ai_prediction = _prediction(sample, result, latency, cost)
        ai_predictions.append(ai_prediction)
        hybrid_predictions.append({
            **rule_prediction,
            **{key: value for key, value in ai_prediction.items() if value not in (None, "", [], {})},
        })
    evaluated_gold = gold[: len(ai_predictions)]
    output.update({
        "ai": {"status": "completed", "metrics": evaluate_records(evaluated_gold, ai_predictions)},
        "hybrid": {"status": "completed", "metrics": evaluate_records(evaluated_gold, hybrid_predictions)},
        "actual_ai_calls": budget.calls, "total_tokens": total_tokens,
        "estimated_cost_usd": budget.estimated_cost_usd, "model": provider.model,
        "prompt_version": provider.prompt_version,
    })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate rule, AI and hybrid P2.2 extraction")
    parser.add_argument("--gold", type=Path, default=ROOT / "evaluation" / "p2_2" / "gold_samples.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "p2_2" / "evaluation_results.json")
    parser.add_argument("--allow-ai", action="store_true")
    parser.add_argument("--ai-limit", type=int, default=20)
    parser.add_argument("--max-cost-usd", type=float, default=5.0)
    args = parser.parse_args()
    result = run(args.gold.resolve(), allow_ai=args.allow_ai, ai_limit=args.ai_limit, max_cost_usd=args.max_cost_usd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
