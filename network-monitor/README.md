# Aegean network monitor

Live **network-map dashboard** with **all session options in the browser** (task, N, expert IDs, full `AegeanConfig`). Agents always run via **OpenRouter** (`OPENROUTER_API_KEY` in `.env`). No CLI prompts—start the server and use the form.

Everything lives in **`network-monitor/`**.

## Start the dashboard

From **`multi-agentic-bft/`** (no `PYTHONPATH`):

```bash
py -3 run_network_monitor.py
```

Optional port: `set AEGEAN_VIZ_PORT=8766` before running.

Module form (needs `PYTHONPATH`):

```bash
set PYTHONPATH=network-monitor
py -3 -m network_monitor
```

On **Git Bash**: `export PYTHONPATH=network-monitor`.

Then open the printed URL (or let the launcher open a browser). Fill the **left panel**; worker transport defaults to **tcp** (persistent session) and **http** is optional, then click **Run Aegean session**. The map, quorum ring, and event log update live; **Run** is disabled while `run_status` is `running` and **Cancel run** is enabled.

## API (localhost)

| Method | Path | Purpose |
|--------|------|--------|
| `GET` | `/` | Web UI |
| `GET` | `/api/state` | JSON snapshot (poll) |
| `GET` | `/api/capabilities` | `{ "openrouter": bool, "model_default": "..." }` |
| `POST` | `/api/run` | JSON body = same fields as the form (see `runner._parse_spec`, includes `transport` and optional semantic fields) |
| `POST` | `/api/cancel` | Request immediate cancellation of the active run |

### Semantic equivalence (optional)

Set `semantic_equivalence_enabled` to `true` in the form or POST body to use SimCSE + HDBSCAN + weighted stability (`AegeanConfig.semantic_equivalence`). Install local ML deps in the **same** Python environment you use to start the monitor:

```bash
pip install 'multi-agentic-bft[semantic]'
```

**Prefetch the SimCSE weights** (recommended once per machine / Python env, same interpreter as above):

```bash
py -3 examples/prefetch_semantic_model.py
```

Set **`HF_TOKEN`** in `.env` if Hub downloads are slow or you hit rate limits. Then start the monitor; semantic runs will reuse the cache instead of downloading mid-session.

Submit validates imports before starting workers. The dashboard uses a **fixed** SimCSE checkpoint (`princeton-nlp/sup-simcse-bert-base-uncased`), **fixed** weighted-stability threshold **2.0**, and **HDBSCAN `min_cluster_size` always follows the session `alpha`** (no separate cluster-size field). Tune quorum / clustering only via **`alpha`**. The **Final outcome** panel shows `semantic_no_consensus` JSON when the run ends on `max_rounds` or `timeout` without commit.

If **Run** returns HTTP 400, open the browser **Console** (`console.error` logs the JSON body), check the **hint** under the button, and watch the **terminal** where you started the monitor (`[aegean-viz] POST /api/run rejected: …`). Typical causes: missing `OPENROUTER_API_KEY`, semantic mode on without `pip install 'multi-agentic-bft[semantic]'`, empty task prompt, or `expert_ids` count not matching **N**.

**CLI cross-check (same OpenRouter + HTTP workers as the monitor’s `http` transport):** from repo root run `python examples/simple_cluster.py --check-env`, then `python examples/simple_cluster.py`. If the script sees the API key but the dashboard does not, restart the monitor after editing `.env`, or align **OpenRouter base port** with `BASE_PORT` in `examples/simple_cluster.py` (default `18700`).

## Preset demo run

Starts the dashboard and **submits** a short OpenRouter session (no form). Requires `OPENROUTER_API_KEY`:

```bash
py -3 run_network_monitor.py demo
```

## HTTP smoke

```bash
py -3 network-monitor/smoke_http.py
```

## `simple_cluster.py` + map only

```bash
set PYTHONPATH=network-monitor
set AEGEAN_VIZ=1
py -3 examples/simple_cluster.py
```

## Layout

| Path | Role |
|------|------|
| `network_monitor/runner.py` | Parse spec, `run_dashboard_session`, OpenRouter workers |
| `network_monitor/viz_session.py` | `VizSession`, `submit_run`, `capabilities` |
| `network_monitor/state.py` | Snapshot + `run_status` |
| `network_monitor/server.py` | HTTP + `POST /api/run` |
| `network_monitor/static/index.html` | Form + canvas |
| `network_monitor/tcp_session.py` | Framed JSON TCP read/write + persistent session client |
| `network_monitor/transport.py` | Session transport abstraction + TCP transport adapter |

## Library integration

Use `VizSession`, `worker_trace`, and `finalize` from your own runner if you embed the dashboard; see `viz_session.py` and `runner.py`.
