# Multi Agentic Consensus Protcol - Aegean Implementation

Lightweight Python coordination library for multi-agent agreement.

You bring model adapters and prompts.  
This library handles leader election, quorum logic, refinement rounds, and consensus stop conditions.

For full technical details, read `DETAILED_GUIDE.md`.

---

## Why use it?

- Coordinate 3+ independent agents on one task.
- Stop based on explicit agreement rules instead of ad-hoc voting.
- Get structured outputs (`AegeanResult`, optional commit certificate).
- Keep runtime dependencies minimal (Python stdlib).

---

## Plain-English Definitions

- **Agent / Expert:** one worker that tries to answer the task. It can be an LLM wrapper, a tool pipeline, or any function-like component with `execute(task)`.
- **Task:** the input question/problem you want the group to solve.
- **Solution (Soln):** each agent's first independent answer to the task.
- **Refinement (Refm):** later rounds where agents improve answers after seeing group context.
- **Leader:** the coordinator for a round. It drives the round flow; it does not own the "truth."
- **Consensus:** enough agents converge on the same normalized answer according to configured thresholds.
- **Certificate:** structured proof of how/why a final answer was accepted.

If "expert" sounds too academic, read it as "worker" or "agent instance."

---

## How it Works (Abstract View)

1. You submit one task and a list of agents.
2. Every agent produces an initial answer (solution phase).
3. The system compares answers and runs refinement rounds when needed.
4. The process stops when agreement rules are met or limits are reached.
5. You get a full run result with final status, trace, and optional certificate.

You can think of it like a "group decision engine" sitting between your app and your model/tool adapters.

---

## Quick Start

### 1) Install

```bash
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

### 2) Minimal run

```python
from aegean import AegeanConfig, EventBus, create_aegean_protocol
from aegean.mocks import ScriptedAegeanAgent

experts = ["a1", "a2", "a3"]
# "experts" here just means independent worker agents.
agents = {name: ScriptedAegeanAgent(soln="same", refm="same") for name in experts}

session_cfg = {
    "session_id": "run-001",
    "pattern": "aegean",
    "experts": experts,
    "task": {"id": "t1", "description": "Answer this", "context": {}},
}

protocol = create_aegean_protocol(
    AegeanConfig(max_rounds=5, alpha=2, beta=2, early_termination=True),
    EventBus(),
)

out = protocol.execute(session_cfg, agents)
assert out["ok"], out.get("error")

result = out["value"]
print(result.consensus_reached, result.termination_reason, result.consensus_value)
```

### 3) Easy agent behaviors you can test right away

`ScriptedAegeanAgent` is a mock agent with two outputs:

- `soln`: what it returns in round 0 (first answer)
- `refm`: what it returns in refinement rounds (later answers)

```python
from aegean.mocks import ScriptedAegeanAgent

# Example: start with disagreement, then converge
a1 = ScriptedAegeanAgent(soln="A", refm="X")
a2 = ScriptedAegeanAgent(soln="B", refm="X")
a3 = ScriptedAegeanAgent(soln="C", refm="X")
```

Round behavior for the example above:

- Round 0 (initial): `A`, `B`, `C` (they disagree)
- Refinement rounds: `X`, `X`, `X` (they converge)
- Protocol can now reach consensus on `X`

If you want dynamic behavior, `soln` and `refm` can also be callables:

```python
def refm_from_context(task):
    r_bar = task["context"]["aegean"]["refinement_set"]
    return f"refined_using_{len(r_bar)}_peer_answers"

dynamic = ScriptedAegeanAgent(soln="first-try", refm=refm_from_context)
```

Use this mock to learn the expected `execute(task)` contract before wiring real model/tool agents.

### 4) Do I need to care about `soln` and `refm`?

Usually, no.

For most users, `soln` and `refm` are protocol-level phases handled internally by `AegeanProtocol`. You generally only need to:

- pass `agents` + `session_cfg` into `protocol.execute(...)`,
- read `result.consensus_reached`, `result.consensus_value`, and `result.termination_reason`.

You only need phase-specific logic if you are implementing custom agent adapters and want different behavior for initial-answer vs refinement rounds.

---

## Core Concepts (Minimal Jargon)

- **Initial answers:** first pass from all agents.
- **Refinement rounds:** extra passes to converge.
- **Agreement check:** by default, two answers match only if their `value["output"]` is equal.
- **Run success vs answer agreement:** `ok=True` means the protocol ran; `result.consensus_reached` means the group agreed.

---

## Agent Contract

Each expert must implement:

```python
def execute(self, task: dict) -> dict:
    return {
        "ok": True,
        "value": {
            "output": "...",
            "metadata": {"confidence": 0.95},
        },
    }
```

Tips:

- Include `task["id"]`.
- Read `task["context"]["aegean"]["phase"]` (`soln`/`refm`) to switch between initial answer vs refinement behavior.
- Keep adapters thread-safe.
- Normalize outputs if semantic equivalence matters.

### What metadata must be returned?

Minimum success shape:

```python
{
    "ok": True,
    "value": {
        "output": "...",  # required
        # "metadata": {...}  # optional
    },
}
```

Minimum failure shape:

```python
{"ok": False, "error": "reason"}
```

Metadata is optional, but these keys are supported by protocol:

- `metadata.confidence` (optional, default `1.0`): if below `AegeanConfig.confidence_threshold`, the response is excluded from accept quorum.
- `metadata.tokens_used` (optional, default `0`): used for token accounting in final results.

Recommended production metadata:

```python
"metadata": {
    "confidence": 0.95,
    "tokens_used": 123,
}
```

---

## Common Next Steps

1. Replace `ScriptedAegeanAgent` with your real model adapters.
2. Tune `AegeanConfig` (`alpha`, `beta`, timeouts, `max_rounds`).
3. Persist `AegeanResult` for traceability and replay checks.
4. Wire `EventBus` to your observability stack.
5. In production, set `environment: "production"` in `session_cfg` (or env var `AEGEAN_ENV=production`) to block `aegean.mocks` agents at runtime.

---

## Production Adapters (HTTP + OpenRouter)

The repo now includes reusable production adapters in `aegean.adapters`:

- `HttpAgent`: generic adapter for any remote `POST /execute` workflow.
- `OpenRouterAgent`: ready-to-use adapter for OpenRouter chat completions.

### Generic HTTP agent wiring

```python
from aegean.adapters import HttpAgent

experts = ["a1", "a2", "a3"]
agents = {
    "a1": HttpAgent(endpoint="http://10.0.0.11:8000/execute"),
    "a2": HttpAgent(endpoint="http://10.0.0.12:8000/execute"),
    "a3": HttpAgent(endpoint="http://10.0.0.13:8000/execute"),
}
```

Expected remote response shape:

```python
{
    "ok": True,
    "value": {
        "output": "answer",
        "metadata": {"confidence": 0.9, "tokens_used": 123},
    },
}
```

If you are building your own adapter, use `HttpAgent` and `OpenRouterAgent` as the reference implementation of the `execute(task)` contract.

### Build-your-own adapter template

```python
from aegean.adapters import ok_result, error_result

class MyCustomAgent:
    def execute(self, task: dict) -> dict:
        try:
            # Call your backend/provider here.
            answer = "..."
            return ok_result(answer, confidence=0.92, tokens_used=180, provider="my-backend")
        except Exception as exc:
            return error_result(f"backend failure: {exc}")
```

---

## Docs Map

- `DETAILED_GUIDE.md` - full protocol internals, configuration semantics, and extension design.
- `checklist.md` - shipped features by module.
- `plan.md` - design rationale and paper mapping.

---

## Project Structure

```text
aegean/
tests/
checklist.md
plan.md
DETAILED_GUIDE.md
```
