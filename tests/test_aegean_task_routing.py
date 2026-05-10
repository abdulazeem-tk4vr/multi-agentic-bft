from aegean.task_routing import (
    PHASE_REFM,
    PHASE_SOLN,
    aegean_task_phase,
    build_refm_task,
    build_soln_task,
    refinement_context,
    refm_task_matches_round,
)
from tests.mocks import ScriptedAegeanAgent


def test_aegean_task_phase_defaults_to_soln():
    task = {"id": "t1", "description": "solve", "context": {}}
    assert aegean_task_phase(task) == PHASE_SOLN


def test_aegean_task_phase_refm():
    task = {
        "id": "t1",
        "description": "refine",
        "context": {"aegean": {"phase": PHASE_REFM, "round_num": 2}},
    }
    assert aegean_task_phase(task) == PHASE_REFM


def test_refinement_context_roundtrip():
    base = {"id": "task-x", "description": "Do reasoning", "context": {}}
    refm = build_refm_task(
        base,
        refinement_set=["a", "b"],
        term_num=1,
        round_num=2,
        agent_id="agent-1",
    )
    bag = refinement_context(refm)
    assert bag is not None
    assert bag["phase"] == PHASE_REFM
    assert bag["refinement_set"] == ["a", "b"]
    assert bag["term_num"] == 1
    assert bag["round_num"] == 2
    assert "refm-t1-r2-agent-1" in refm["id"]


def test_build_soln_task_includes_agent_id_when_passed():
    base = {"id": "t", "description": "d", "context": {}}
    soln = build_soln_task(base, round_num=0, agent_id="expert-2")
    assert soln["context"]["aegean"]["agent_id"] == "expert-2"


def test_build_refm_task_includes_agent_id_in_aegean_bag():
    base = {"id": "t", "description": "d", "context": {}}
    refm = build_refm_task(base, refinement_set=[], term_num=1, round_num=1, agent_id="z")
    assert refm["context"]["aegean"]["agent_id"] == "z"


def test_build_soln_task_tags_context():
    base = {"id": "root", "description": "Q", "context": {"extra": 1}}
    soln = build_soln_task(base, round_num=0)
    assert aegean_task_phase(soln) == PHASE_SOLN
    assert soln["context"]["aegean"]["round_num"] == 0
    assert soln["context"]["extra"] == 1


def test_refm_task_matches_round():
    base = {"id": "task-x", "description": "Do reasoning", "context": {}}
    ok = build_refm_task(base, refinement_set=[1], term_num=1, round_num=4, agent_id="agent-1")
    assert refm_task_matches_round(ok, 4) is True
    assert refm_task_matches_round(ok, 3) is False
    assert refm_task_matches_round(build_soln_task(base), 99) is True


def test_scripted_agent_dispatches_soln_and_refm():
    agent = ScriptedAegeanAgent(soln="S-OUT", refm="R-OUT")
    base = {"id": "t", "description": "x", "context": {}}
    assert agent.execute(build_soln_task(base))["value"]["output"] == "S-OUT"
    refm_task = build_refm_task(base, refinement_set=[1], term_num=1, round_num=1, agent_id="a")
    assert agent.execute(refm_task)["value"]["output"] == "R-OUT"


def test_scripted_agent_callable_refm_sees_r_bar():
    def refm(task: dict):
        bag = task["context"]["aegean"]
        return f"joined:{bag['refinement_set']}"

    agent = ScriptedAegeanAgent(soln="s", refm=refm)
    base = {"id": "t", "description": "x", "context": {}}
    task = build_refm_task(base, refinement_set=["x", "y"], term_num=0, round_num=3, agent_id="z")
    assert agent.execute(task)["value"]["output"] == "joined:['x', 'y']"
