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

Then open the printed URL (or let the launcher open a browser). Fill the **left panel**, click **Run Aegean session**. The map, quorum ring, and event log update live; **Run** is disabled while `run_status` is `running` and **Cancel run** is enabled.

## API (localhost)

| Method | Path | Purpose |
|--------|------|--------|
| `GET` | `/` | Web UI |
| `GET` | `/api/state` | JSON snapshot (poll) |
| `GET` | `/api/capabilities` | `{ "openrouter": bool, "model_default": "..." }` |
| `POST` | `/api/run` | JSON body = same fields as the form (see `runner._parse_spec`) |
| `POST` | `/api/cancel` | Request immediate cancellation of the active run |

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

## Library integration

Use `VizSession`, `worker_trace`, and `finalize` from your own runner if you embed the dashboard; see `viz_session.py` and `runner.py`.
