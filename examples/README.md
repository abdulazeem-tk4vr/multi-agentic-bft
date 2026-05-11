# Runnable examples

From the package root (`multi-agentic-bft/`), install in editable mode so `import aegean` works:

```bash
python -m pip install -e ".[dev]"
```

**`simple_cluster.py`** — starts **one HTTP worker per expert** on `127.0.0.1`, each calling **OpenRouter** via **`OpenRouterAgent`**. Set **`OPENROUTER_API_KEY`** in the environment or in **`.env`** (see below). Optional **`OPENROUTER_MODEL`**. With **`VERBOSE=True`**, enables **`AegeanConfig(session_trace=True)`** so the **library** prints the full session trace to **stderr** (or set **`AEGEAN_SESSION_TRACE=1`** on any **`run_aegean_session`** call).

**`.env` search order** (same idea as the network monitor): `multi-agentic-bft/.env`, then `multi-agentic-bft/network-monitor/.env`, then `<current working directory>/.env`. Existing environment variables are not overwritten.

**Troubleshooting the dashboard (`POST /api/run` 400):** run **`python examples/simple_cluster.py --check-env`** from the repo root (or anywhere) to see which `.env` files exist and whether `OPENROUTER_API_KEY` is visible. Then run **`python examples/simple_cluster.py`** — if that works but the browser does not, the monitor process likely needs a restart after you add `.env`, or a port conflict on `18700–18702`.

**`prefetch_semantic_model.py`** — downloads the default SimCSE checkpoint into the Hugging Face cache **before** you start the dashboard, so the first semantic run does not sit on a progress bar (or get interrupted if you cancel). Use the **same** Python as the monitor: **`py -3 examples/prefetch_semantic_model.py`**. Optional **`HF_TOKEN`** in `.env` for faster Hub downloads.

**`consensus_entry.py`** — same protocol call with **in-process** `ScriptedAegeanAgent` (no HTTP). **`python examples/consensus_entry.py`**

## HTTP workers (manual, one terminal per port)

```bash
python examples/minimal_http_execute_server.py 8081
python examples/minimal_http_execute_server.py 8082
python examples/minimal_http_execute_server.py 8083
```

See the main **`README.md`** section *HTTP workers*.
