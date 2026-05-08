import pytest

from aegean.decision_engine import (
    DecisionEngine,
    DecisionEngineConfig,
    cluster_by_alpha_equivalence,
)


def test_cluster_by_alpha_equivalence():
    same = lambda a, b: abs(a - b) < 2  # type: ignore[no-redef]
    out = cluster_by_alpha_equivalence([1, 2, 10], same)
    lengths = sorted(len(c) for c in out)
    assert lengths == [1, 2]


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        DecisionEngine(DecisionEngineConfig(alpha=0, beta=1))
    with pytest.raises(ValueError):
        DecisionEngine(DecisionEngineConfig(alpha=1, beta=0))


def test_no_alpha_support_resets_candidate():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    r = eng.step(r_bar_prev=["a"], current_round_outputs=["a", "b", "c"])
    assert not r.committed
    assert r.stability == 0
    assert r.eligible_candidate is None


def test_alpha_winner_not_in_prev_yields_no_eligible():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    r = eng.step(r_bar_prev=["z"], current_round_outputs=["y", "y"])
    assert r.eligible_candidate is None
    assert r.stability == 0


def test_figure5_fast_path_two_rounds():
    """Case 1 sketch: same candidate meets α for two consecutive rounds; β=2 commits."""
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    eng.on_new_term(1)
    r1 = eng.step(r_bar_prev=["sol"], current_round_outputs=["noise", "sol", "sol"])
    assert not r1.committed
    assert r1.stability == 1
    assert r1.eligible_candidate == "sol"
    r2 = eng.step(r_bar_prev=["sol", "noise"], current_round_outputs=["sol", "sol"])
    assert r2.committed
    assert r2.value == "sol"
    assert r2.stability == 2


def test_figure5_overturn_resets_stability_to_one():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    eng.on_new_term(1)
    eng.step(r_bar_prev=["a", "b"], current_round_outputs=["a", "a"])
    r = eng.step(r_bar_prev=["a", "b"], current_round_outputs=["b", "b"])
    assert r.overturned
    assert r.stability == 1
    assert not r.committed
    r2 = eng.step(r_bar_prev=["a", "b"], current_round_outputs=["b", "b"])
    assert r2.committed and r2.value == "b"


def test_committed_member_of_r_bar_prev():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    eng.on_new_term(1)
    prev = ["p1", "p2"]
    eng.step(r_bar_prev=prev, current_round_outputs=["p2", "p2"])
    r = eng.step(r_bar_prev=prev, current_round_outputs=["p2", "p2"])
    assert r.committed
    assert r.value in prev


def test_new_term_clears_beta_state():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=2))
    eng.on_new_term(1)
    eng.step(r_bar_prev=["a"], current_round_outputs=["a", "a"])
    eng.on_new_term(2)
    r = eng.step(r_bar_prev=["a"], current_round_outputs=["a", "a"])
    assert r.stability == 1 and not r.committed


def test_beta_one_commits_first_eligible_round():
    eng = DecisionEngine(DecisionEngineConfig(alpha=2, beta=1))
    eng.on_new_term(1)
    r = eng.step(r_bar_prev=["x"], current_round_outputs=["x", "x"])
    assert r.committed and r.value == "x"


def test_custom_alpha_equivalence():
    eng = DecisionEngine(
        DecisionEngineConfig(alpha=2, beta=2),
        alpha_same=lambda a, b: str(a).lower() == str(b).lower(),
    )
    eng.on_new_term(1)
    r1 = eng.step(r_bar_prev=["aa"], current_round_outputs=["AA", "aa", "bb"])
    assert r1.eligible_candidate == "aa"
    assert r1.stability == 1
