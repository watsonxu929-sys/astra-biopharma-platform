from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.base import ProviderUnavailable
from app.services.ai_budget import AIBudgetExceeded, AIPilotBudget
from app.services.collectors.playwright_adapter import PlaywrightAdapter, PlaywrightUnavailable
from app.services.content_quality_service import assess_content_quality
from app.services.evaluation_service import compare_modes, evaluate_records, precision_recall_f1
from app.services.parsers.document_parser import DocumentParser
from app.services.parsers.base import ParserUnavailable
from app.settings import resolved_db_path


def test_quality_gate_accepts_article_and_rejects_noise_and_duplicates():
    accepted = assess_content_quality(
        title="FDA approves a therapy", source_url="https://www.fda.gov/example",
        published_at="2025-01-30", language="en", text="Evidence-based regulatory article. " * 30,
    )
    assert accepted.status == "accepted"
    assert accepted.accepted_for_analysis is True
    duplicate = assess_content_quality(
        title="same", source_url="https://example.test/item", text="body " * 100,
        duplicate_score=0.99,
    )
    assert duplicate.status == "duplicate"
    assert duplicate.accepted_for_analysis is False
    denied = assess_content_quality(
        title="Sign in", source_url="https://example.test/login", text="Log in. Forgot password.",
        http_status=403,
    )
    assert denied.status == "access_denied"


def test_playwright_is_optional_and_dynamic_only(monkeypatch):
    adapter = PlaywrightAdapter()
    with pytest.raises(ValueError, match="playwright_requires_dynamic_source"):
        adapter.fetch("https://example.test", dynamic=False)
    monkeypatch.setattr("app.services.collectors.playwright_adapter.importlib.util.find_spec", lambda name: None)
    with pytest.raises(PlaywrightUnavailable, match="playwright_unavailable"):
        adapter.fetch("https://example.test", dynamic=True)


def test_docling_is_optional_and_oversize_is_rejected(tmp_path, monkeypatch):
    parser = DocumentParser()
    monkeypatch.setattr("app.services.parsers.document_parser.importlib.util.find_spec", lambda name: None)
    with pytest.raises(ParserUnavailable, match="docling_parser_unavailable"):
        parser.parse({"attachment_path": str(tmp_path / "missing.pdf"), "content_type": "application/pdf"})
    sample = tmp_path / "large.pdf"
    sample.write_bytes(b"x" * 11)
    monkeypatch.setattr("app.services.parsers.document_parser.importlib.util.find_spec", lambda name: object())
    with pytest.raises(ParserUnavailable, match="document_too_large"):
        parser.parse({"attachment_path": str(sample), "content_type": "application/pdf", "max_file_bytes": 10})


def test_ai_key_and_budget_limits(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailable, match="openai_api_key_unavailable"):
        OpenAIProvider().analyze("text")
    budget = AIPilotBudget(max_calls=1, max_cost_usd=0.01)
    budget.reserve("openai")
    with pytest.raises(AIBudgetExceeded, match="ai_call_limit_exceeded"):
        budget.reserve("openai")
    budget = AIPilotBudget(max_calls=20, max_cost_usd=0.001)
    budget.record_usage({"input_tokens": 1000}, input_cost_per_million=2.0)
    with pytest.raises(AIBudgetExceeded, match="ai_budget_exceeded"):
        budget.reserve("openai")


def test_evaluation_metrics_are_zero_safe_and_comparable():
    assert precision_recall_f1([], []) == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    empty = evaluate_records([], [])
    assert empty["sample_count"] == 0
    assert empty["event_classification_accuracy"] == 0.0
    gold = [{
        "sample_id": "1", "text": "FDA approved Drug A.", "event_type": "approval",
        "organizations": ["FDA"], "people": [], "products": ["Drug A"],
    }]
    prediction = [{
        "sample_id": "1", "event_type": "approval", "organizations": ["FDA"], "people": [],
        "products": ["Drug A"], "candidates": [{"evidence_excerpt": "FDA approved Drug A.", "char_start": 0}],
    }]
    compared = compare_modes(gold, {"rule": prediction, "ai": [], "hybrid": prediction})
    assert compared["rule"]["event_classification_accuracy"] == 1.0
    assert compared["rule"]["evidence_coverage"] == 1.0
    assert compared["rule"]["hallucination_rate"] == 0.0
    assert set(compared) == {"rule", "ai", "hybrid"}


def test_004_migration_is_idempotent_on_copy_and_formal_db_unchanged(tmp_path):
    formal = resolved_db_path().resolve()
    before = hashlib.sha256(formal.read_bytes()).hexdigest()
    copy = tmp_path / "pilot.db"
    shutil.copy2(formal, copy)
    spec = importlib.util.spec_from_file_location(
        "migration004", Path(__file__).parents[1] / "scripts" / "migrations" / "004_real_source_quality_evaluation.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    with sqlite3.connect(copy) as conn:
        conn.execute("BEGIN IMMEDIATE")
        module.apply_schema(conn)
        conn.commit()
        first = module.analyze(conn)
        module.apply_schema(conn)
        second = module.analyze(conn)
    assert not first["missing_required_tables"]
    assert all(not value for value in first["missing_columns"].values())
    assert first == second
    assert hashlib.sha256(formal.read_bytes()).hexdigest() == before


def test_gold_set_has_bounded_real_samples():
    path = Path(__file__).parents[1] / "evaluation" / "p2_2" / "gold_samples.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert 10 <= len(rows) <= 20
    assert len({row["sample_id"] for row in rows}) == len(rows)
    assert all(row["source_url"].startswith("https://") and row["evidence_fragments"] for row in rows)
