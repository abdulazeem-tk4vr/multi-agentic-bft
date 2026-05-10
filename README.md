# Multi-agentic consensus (Aegean)

Python library for coordinating **3+ agents** on one task: leader election, quorums, Soln / Refm rounds, and **α / β** commit rules. You supply **`execute(task)`** adapters (local classes or **HTTP** workers); you get an **`AegeanResult`**. **Stdlib only** at runtime.

**Internals:** `DETAILED_GUIDE.md`

---

## Install

```bash
cd multi-agentic-bft
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

Run **`python examples/simple_cluster.py`** to auto-start local **`/execute`** workers backed by **OpenRouter** (**`OPENROUTER_API_KEY`** required), or **`python examples/consensus_entry.py`** for in-process mocks. See **`examples/README.md`**.

---

## Entry script (typical use)

**Single API:** `run_aegean_session(session_cfg, agents, config=AegeanConfig(...), event_bus=EventBus())` → **`AegeanResult`**.

Same code lives in **`examples/consensus_entry.py`** — run it or copy into your app. **`experts`** order sets the round-0 leader (**`experts[0]`**). **`experts`** and **`agents`** must match exactly (same ids, no extras, no duplicates in **`experts`**).

```python
#!/usr/bin/env python3
"""Minimal entry: local mock agents. Swap agents for http_agents_from_endpoints({...}) for remote workers."""

from aegean import AegeanConfig, EventBus, run_aegean_session
from aegean.mocks import ScriptedAegeanAgent

def main() -> None:
    experts = ["a1", "a2", "a3"]

    agents = {
        "a1": ScriptedAegeanAgent(soln="same", refm="same"),
        "a2": ScriptedAegeanAgent(soln="same", refm="same"),
        "a3": ScriptedAegeanAgent(soln="same", refm="same"),
    }

    session_cfg = {
        "session_id": "run-001",
        "pattern": "aegean",
        "experts": experts,
        "task": {
            "id": "t1",
            "description": "Your question or prompt for all agents.",
            "context": {},
        },
    }

    result = run_aegean_session(
        session_cfg,
        agents,
        config=AegeanConfig(
            max_rounds=5,
            alpha=2,
            beta=2,
            early_termination=True,
        ),
        event_bus=EventBus(),
    )

    print("consensus_reached:", result.consensus_reached)
    print("termination_reason:", result.termination_reason)
    print("consensus_value:", result.consensus_value)
    if result.commit_certificate:
        print("certificate:", result.commit_certificate)


if __name__ == "__main__":
    main()
```

- **`AegeanSessionError`** — roster/election/setup failed before a normal **`AegeanResult`**.
- **`consensus_reached=False`** — run finished but α/β commit was not reached (not an exception).

**Cancel or many sessions on one bus:** `AegeanRunner` — `runner.run(session_cfg, agents)` and `runner.cancel()`. After cancel, create a new runner.

**Raw `{"ok", "error"}`:** `create_aegean_protocol(...); protocol.execute(session_cfg, agents)`.

---

## HTTP workers (IPs / hosts)

Same **`run_aegean_session`** call; only **`agents`** changes:

```python
from aegean import AegeanConfig, EventBus, run_aegean_session, http_agents_from_endpoints

experts = ["worker-a", "worker-b", "worker-c"]
agents = http_agents_from_endpoints(
    {
        "worker-a": "10.0.0.11:8080",              # → http://10.0.0.11:8080/execute
        "worker-b": "10.0.0.12:8080",
        "worker-c": "https://10.0.0.13/custom",   # path preserved if not "/"
    },
    execute_path="/execute",
    timeout_s=60.0,
)

session_cfg = {
    "session_id": "s1",
    "pattern": "aegean",
    "experts": experts,
    "task": {"id": "t1", "description": "…", "context": {}},
}

result = run_aegean_session(
    session_cfg,
    agents,
    config=AegeanConfig(max_rounds=5, alpha=2, beta=2),
    event_bus=EventBus(),
)
```

Each worker: **POST** body `{"task": <dict>, "agent_id": "<id>"}`; response = same shape as local **`execute`** (`ok` / `value` / `error`). Local stub workers: `python examples/minimal_http_execute_server.py 8081` (see `examples/README.md`).

**Helpers:** `normalize_agent_endpoint(...)`, `HttpAgent(endpoint=...)`.

**Production:** set `environment: "production"` in **`session_cfg`** or **`AEGEAN_ENV=production`** to block mocks.

**OpenRouter:** **`examples/simple_cluster.py`** uses **`OpenRouterAgent`** for each worker; set **`OPENROUTER_API_KEY`** (and optionally **`OPENROUTER_MODEL`**). Remote workers still use **POST** **`{"task": <dict>, "agent_id": <id>}`** and return the same **`execute`** JSON as **`minimal_http_execute_server`**.

---

## Session layout

| Piece | Role |
|-------|------|
| **`session_cfg`** | `session_id`, **`experts`** (ordered list), **`task`** (`id`, `description`, `context`), optional `recovery`, `election_messenger`, … |
| **`agents`** | `dict[expert_id, agent]` with **`execute(task) -> dict`** |
| **`AegeanConfig`** | **`alpha`**, **`beta`**, **`max_rounds`**, timeouts, **`byzantine_tolerance`**, **`confidence_threshold`**, **`session_trace`**, … |

**Validation:** `set(experts) == set(agents.keys())`, no duplicate ids in **`experts`**, **≥ 3** experts for default paper bounds.

**Session trace:** `AegeanConfig(session_trace=True)` or env **`AEGEAN_SESSION_TRACE=1`** (also **`true`**, **`yes`**, **`on`**) prints a human-readable run summary to **stderr** after **`run_aegean_session`** / **`AegeanRunner.run`**. Programmatic: **`print_session_trace`** from **`aegean`**.

The coordinator calls **`execute(task)`** per round (it does not spawn processes). **`task`** includes **`context.aegean`**: **`phase`** `soln` / `refm`, **`refinement_set`**, **`agent_id`**, etc.

---

## Agent `execute` contract

```python
def execute(self, task: dict) -> dict:
    return {
        "ok": True,
        "value": {
            "output": ...,  # required
            "metadata": {"confidence": 0.92, "tokens_used": 150},  # optional
        },
    }
    # or {"ok": False, "error": "reason"}
```

Use **`from aegean.adapters import ok_result, error_result`** in your adapters.

**Example `task` (Soln):** `context.aegean` has `phase`, `round_num`, `agent_id`. **Refm** adds `refinement_set`, `term_num`, `round_num`.

**Mock:** `ScriptedAegeanAgent(soln=..., refm=...)`.

---

## More docs

- **`DETAILED_GUIDE.md`** — full protocol
- **`checklist.md`**, **`original_plan.md`**

```text
aegean/   examples/   tests/
```
