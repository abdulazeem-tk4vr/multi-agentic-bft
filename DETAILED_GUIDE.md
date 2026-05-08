# multi-agentic-bft Detailed Guide

This guide explains the full protocol behavior, extension points, and operational expectations for `multi-agentic-bft`.

If you are new to the project, start with `README.md` first, then come back here.

---

## What You Get

You provide:

- prompts and model/tool backends,
- task payload semantics,
- app-level policy and approvals.

This library provides:

- leader election,
- quorum and acceptance logic,
- round orchestration (Soln + Refm),
- consensus commit semantics using `alpha`/`beta`,
- structured run outputs (`AegeanResult`, optional `CommitCertificate`).

---

## Core Terms

| Term | Meaning |
|------|---------|
| `N` | Number of experts in `session_cfg["experts"]` |
| `f` | Fail-stop tolerance (`AegeanConfig.byzantine_tolerance`) |
| `R` | Quorum threshold (`N - f`) |
| Soln (Round 0) | Initial answer collection |
| Refm (Round >= 1) | Refinement rounds coordinated by leader |
| `alpha` | Minimum matching cluster size in a round |
| `beta` | Consecutive stable rounds to commit |

Agreement matching is equality on `value["output"]`. If you need semantic matching, normalize output in adapters before returning.

---

## Execute Lifecycle

`AegeanProtocol.execute` performs:

1. Validation (`N >= 3`, bounded `f`, experts present).
2. Optional recovery payload handling.
3. Leader election (in-process or messenger transport).
4. Soln collection with parallel agent execution.
5. Refinement rounds + decision engine updates.
6. Return of `AegeanResult` (with full trace and termination reason).

Per-step execution is parallelized and constrained by `round_timeout_ms`.

---

## Return Contract

`execute` returns:

```python
{
  "ok": bool,
  "value": AegeanResult,  # only when ok=True
  "error": str,           # only when ok=False
}
```

- `ok=False`: protocol setup/execution failure.
- `ok=True`: protocol completed normally (consensus may still be false).

Check:

- `result.consensus_reached`
- `result.termination_reason`
- `result.rounds`

---

## Agent Contract

Any adapter exposing `execute(task: dict) -> dict`:

```python
def execute(self, task: dict) -> dict:
    return {
        "ok": True,
        "value": {
            "output": "...",
            "metadata": {"confidence": 0.95, "tokens_used": 123},
        },
    }
```

Required adapter behavior:

- handle both phases via `task["context"]["aegean"]["phase"]`,
- keep thread-safe execution,
- include normalized/stable `output`,
- use `confidence` consistently if thresholding is enabled.

Helper APIs: `build_soln_task`, `build_refm_task`, `aegean_task_phase`, `refinement_context`.

---

## Session Config

Required:

- `session_id`
- `pattern="aegean"`
- `experts` (length >= 3)
- `task` (include `id`)

Advanced:

- `recovery`
- `election_messenger`
- `election_initial_terms`
- `refm_round_track_init`
- `max_election_attempts`

See `aegean/protocol.py` for full docstring details.

---

## Config Tuning

| Config | Practical impact |
|--------|------------------|
| `max_rounds` | latency/cost ceiling |
| `round_timeout_ms` | slow-agent tolerance |
| `alpha` | strictness of agreement |
| `beta` | commit stability requirement |
| `early_termination` | spend reduction on fast convergence |
| `byzantine_tolerance` | fail-stop safety assumption |
| `confidence_threshold` | low-confidence filtering |
| `max_election_attempts` | election liveness budget |

---

## Extension Points

1. **Real model adapters**: map your providers into the agent contract.
2. **Output canonicalization**: make agreement semantics meaningful.
3. **Custom election transport**: use message bus/network transport.
4. **Recovery**: persist and replay new-term acknowledgment state.
5. **Policy layer integration**: keep trust/compliance controls above protocol.

The current decision engine uses equality clustering by default; deeper semantics usually require extending `decision_engine.py` and protocol wiring.

---

## Production Adapter Reference

Reference implementations:

- `aegean/adapters/http_agent.py` (`HttpAgent`) for generic HTTP workflows.
- `aegean/adapters/openrouter_agent.py` (`OpenRouterAgent`) for OpenRouter-backed inference.
- `aegean/adapters/base.py` (`ok_result`, `error_result`) helper utilities for custom adapters.

Use these modules as canonical examples for implementing `execute(task)` in production.

---

## Observability

Pass `EventBus` to `create_aegean_protocol`. Event topics include:

- `protocol.started`
- `protocol.completed`
- `protocol.iteration`
- `protocol.aegean.round_started`
- `protocol.aegean.vote_collected`
- `protocol.aegean.quorum_detected`

Default bus captures emitted events in memory for tests; production systems can bridge `emit` into telemetry sinks.

---

## Replay and Cost Utilities

```python
from aegean import validate_aegean_result_replay, inference_reduction_vs_fixed_schedule
```

- `validate_aegean_result_replay(result)`: verify trace invariants.
- `inference_reduction_vs_fixed_schedule(...)`: rough token/round comparison utility.

---

## Repository Map

```text
aegean/
  protocol.py
  types.py
  task_routing.py
  decision_engine.py
  election.py
  election_transport.py
  election_http.py
  refinement_state.py
  helpers_utils.py
  events.py
  commit_semantics.py
  benchmark.py
  logutil.py
tests/
checklist.md
plan.md
```

---

## Operational Limits

- Fault model is fail-stop oriented, not full malicious-adversary defense.
- Agreement quality depends on output normalization quality.
- Security, compliance, and human approvals should be enforced by the host application.

---

## Related Docs

- `README.md`: quick onboarding and usage.
- `checklist.md`: implementation completeness.
- `plan.md`: paper mapping and rationale.
