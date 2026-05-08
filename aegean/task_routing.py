"""Paper Aegean task routing: distinguish initial **Soln** (round 0) vs **Refm** (refinement on ``R̄``).

Executors should receive tasks tagged via ``context["aegean"]`` so mock and production agents can branch
without ``vote-`` / string hacks.
"""

from __future__ import annotations

import json
from typing import Any, Literal

PHASE_SOLN: Literal["soln"] = "soln"
PHASE_REFM: Literal["refm"] = "refm"
AegeanTaskPhase = Literal["soln", "refm"]


def aegean_task_phase(task: dict[str, Any]) -> AegeanTaskPhase:
    """Return **soln** unless ``context.aegean.phase`` is **refm**."""
    ctx = task.get("context")
    if not isinstance(ctx, dict):
        return PHASE_SOLN
    bag = ctx.get("aegean")
    if not isinstance(bag, dict):
        return PHASE_SOLN
    p = bag.get("phase")
    return PHASE_REFM if p == PHASE_REFM else PHASE_SOLN


def refm_task_matches_round(task: dict[str, Any], expected_round: int) -> bool:
    """True if a Refm task targets ``expected_round`` (leader/ref-round alignment check)."""
    if aegean_task_phase(task) != PHASE_REFM:
        return True
    bag = refinement_context(task)
    if not bag:
        return False
    return int(bag.get("round_num", -999999)) == int(expected_round)


def refinement_context(task: dict[str, Any]) -> dict[str, Any] | None:
    """Return the ``aegean`` payload for Refm tasks, or ``None`` if missing."""
    if aegean_task_phase(task) != PHASE_REFM:
        return None
    ctx = task.get("context") or {}
    bag = ctx.get("aegean")
    return bag if isinstance(bag, dict) else None


def build_soln_task(
    base: dict[str, Any],
    *,
    round_num: int = 0,
    task_suffix: str | None = None,
) -> dict[str, Any]:
    """Tag **round 0** (bootstrap) work; same logical input as paper **Task → Soln**."""
    ctx: dict[str, Any] = dict(base.get("context") or {})
    aegean: dict[str, Any] = dict(ctx.get("aegean") or {})
    aegean.update({"phase": PHASE_SOLN, "round_num": int(round_num)})
    ctx["aegean"] = aegean
    suffix = task_suffix if task_suffix is not None else f"soln-r{round_num}"
    tid = f"{base['id']}-{suffix}" if suffix else base["id"]
    return {**base, "id": tid, "context": ctx}


def build_refm_task(
    base: dict[str, Any],
    *,
    refinement_set: list[Any],
    term_num: int,
    round_num: int,
    agent_id: str,
    refinement_set_label: str = "Refinement set (R̄)",
) -> dict[str, Any]:
    """Build a refinement reasoning task for one agent (paper **RefmSet** → **Refm**)."""
    ctx = dict(base.get("context") or {})
    aegean: dict[str, Any] = dict(ctx.get("aegean") or {})
    aegean.update(
        {
            "phase": PHASE_REFM,
            "refinement_set": list(refinement_set),
            "term_num": int(term_num),
            "round_num": int(round_num),
        }
    )
    ctx["aegean"] = aegean
    r_bar = json.dumps(refinement_set, indent=2, default=str)
    desc = (
        f"{base.get('description', '')}\n\n{refinement_set_label} for term {term_num}, "
        f"round {round_num}:\n{r_bar}"
    ).strip()
    tid = f"{base['id']}-refm-t{term_num}-r{round_num}-{agent_id}"
    return {**base, "id": tid, "description": desc, "context": ctx}


