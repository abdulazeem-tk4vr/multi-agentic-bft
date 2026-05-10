# Runnable examples

From the package root (`multi-agentic-bft/`), install in editable mode so `import aegean` works:

```bash
python -m pip install -e ".[dev]"
```

**`simple_cluster.py`** — starts **one HTTP worker per expert** on `127.0.0.1`, each calling **OpenRouter** via **`OpenRouterAgent`**. Set **`OPENROUTER_API_KEY`** in the environment or in **`multi-agentic-bft/.env`**. Optional **`OPENROUTER_MODEL`**. With **`VERBOSE=True`**, enables **`AegeanConfig(session_trace=True)`** so the **library** prints the full session trace to **stderr** (or set **`AEGEAN_SESSION_TRACE=1`** on any **`run_aegean_session`** call). Run: **`python examples/simple_cluster.py`**.

**`consensus_entry.py`** — same protocol call with **in-process** `ScriptedAegeanAgent` (no HTTP). **`python examples/consensus_entry.py`**

## HTTP workers (manual, one terminal per port)

```bash
python examples/minimal_http_execute_server.py 8081
python examples/minimal_http_execute_server.py 8082
python examples/minimal_http_execute_server.py 8083
```

See the main **`README.md`** section *HTTP workers*.
