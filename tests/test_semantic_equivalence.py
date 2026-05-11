"""Unit tests for semantic equivalence (no Hugging Face downloads; uses ``semantic_encode_fn``)."""

from __future__ import annotations

import numpy as np
import pytest

from aegean.semantic_equivalence import (
    SemanticSessionAccumulator,
    SemanticStabilityTracker,
    extract_conclusion,
    run_semantic_decision_step,
)
from aegean.task_routing import build_refm_task
from aegean.types import SemanticEquivalenceConfig


def test_extract_conclusion_str_and_dict():
    assert extract_conclusion("  x  ") == "x"
    assert extract_conclusion({"final_answer": 42}) == "42"
    assert extract_conclusion({"answer": "y"}) == "y"
    assert extract_conclusion({"other": 1}) == str({"other": 1})


def test_semantic_stability_tracker_resets_on_new_term():
    tr = SemanticStabilityTracker(2.0, n_experts=3)
    tr.on_new_term(1)
    r = tr.apply_round(skip=False, eligible="A", sum_sv_dominant=2.0)
    assert r.stability_score == pytest.approx(2.0 / 3.0)
    tr.on_new_term(2)
    assert tr.running_score == 0.0
    assert tr.peek_tracked_candidate() is None


def test_semantic_stability_candidate_flip_resets_then_adds():
    tr = SemanticStabilityTracker(10.0, n_experts=3)
    tr.on_new_term(1)
    tr.apply_round(skip=False, eligible="A", sum_sv_dominant=1.5)
    assert tr.running_score == pytest.approx(0.5)
    tr.apply_round(skip=False, eligible="B", sum_sv_dominant=1.5)
    assert tr.running_score == pytest.approx(0.5)


def test_sv_singleton_dominant_no_divzero():
    """Dominant cluster size 1 with alpha=1 still runs SV path."""
    cfg = SemanticEquivalenceConfig(enabled=True, stability_score_threshold=10.0)
    tr = SemanticStabilityTracker(cfg.stability_score_threshold, n_experts=1)
    tr.on_new_term(1)

    def enc(texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0]], dtype=np.float64)

    from aegean.semantic_equivalence import SimCSEEmbedder

    decision, dissent, skip, inc = run_semantic_decision_step(
        accepted=[("a", "only")],
        r_bar_prev=["only"],
        alpha=1,
        n_experts=1,
        sem_cfg=cfg,
        embedder=SimCSEEmbedder("unused"),
        encode_fn=enc,
        tracker=tr,
    )
    assert skip is False
    assert decision.eligible_candidate == "only"
    assert inc == pytest.approx(1.0)


def test_skip_dominant_below_alpha_no_tracker_mutation():
    """One accept cannot meet α=2 → skip without mutating prior tracker score."""
    cfg = SemanticEquivalenceConfig(enabled=True, stability_score_threshold=2.0)
    tr = SemanticStabilityTracker(cfg.stability_score_threshold, n_experts=3)
    tr.on_new_term(1)
    tr.apply_round(skip=False, eligible="seed", sum_sv_dominant=3.0)
    before = tr.running_score

    def enc(texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0]], dtype=np.float64)

    from aegean.semantic_equivalence import SimCSEEmbedder

    decision, dissent, skip, inc = run_semantic_decision_step(
        accepted=[("e1", "a")],
        r_bar_prev=["a"],
        alpha=2,
        n_experts=3,
        sem_cfg=cfg,
        embedder=SimCSEEmbedder("unused"),
        encode_fn=enc,
        tracker=tr,
    )
    assert skip is True
    assert inc == 0.0
    assert tr.running_score == before
    assert "a" in dissent


def test_build_refm_task_reference_answer_block():
    base = {"id": "tid", "description": "Q", "context": {}}
    t = build_refm_task(
        base,
        refinement_set=["x"],
        term_num=1,
        round_num=2,
        agent_id="ag1",
        reference_answer="central answer",
    )
    assert "Semantic reference" in t["description"]
    assert "central answer" in t["description"]
    assert t["context"]["aegean"].get("reference_answer") == "central answer"


def test_semantic_session_accumulator_payload():
    acc = SemanticSessionAccumulator(stability_threshold=2.0)
    acc.record_round(
        accepted=[("e1", "A"), ("e2", "A")],
        skip_round=False,
        candidate="A",
        increment=0.5,
        dissent=["B"],
    )
    acc.record_round(
        accepted=[("e1", "B"), ("e2", "B")],
        skip_round=False,
        candidate="B",
        increment=0.25,
        dissent=["A"],
    )
    p = acc.to_no_consensus_payload(
        max_rounds=5,
        last_running_score=0.1,
        last_tracked=None,
    )
    assert p["status"] == "no_consensus"
    assert p["rounds_completed"] == 5
    assert p["candidate"] == "A"
    assert "cluster_results" in p and len(p["cluster_results"]) >= 1
    assert "B" in p["minority_signals"]
