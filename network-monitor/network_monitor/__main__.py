"""Start network monitor."""

from __future__ import annotations

import os
import sys
import time
import webbrowser
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
_PKG = _HERE.parents[1]
for p in (_REPO, _PKG):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from network_monitor import VizSession


DEMO_SPEC = {
    "session_id": "viz-demo",
    "n_agents": 3,
    "expert_ids": "",
    "task_id": "t1",
    "task_description": "Pick a one-word codename.",
    "openrouter_base_port": 18_700,
    "transport": "tcp",
    "max_rounds": 5,
    "alpha": 2,
    "beta": 2,
    "byzantine_tolerance": 0,
    "confidence_threshold": 0.7,
    "round_timeout_ms": 60_000,
    "early_termination": True,
    "session_trace": False,
    "max_election_attempts": 32,
    "semantic_equivalence_enabled": False,
}


def main() -> None:
    port = int(os.environ.get("AEGEAN_VIZ_PORT", "8765"))
    viz = VizSession(port=port, repo_root=_REPO)
    url = viz.start()
    print("Aegean network monitor:", url, flush=True)
    print("Configure the session in the browser, then click Run.", flush=True)
    try:
        webbrowser.open(url)
    except OSError:
        pass

    if len(sys.argv) > 1 and sys.argv[1].lower() in ("demo", "--demo"):
        viz.submit_run(DEMO_SPEC)
        print("Submitted demo run (OpenRouter). Requires OPENROUTER_API_KEY in .env.", flush=True)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("", flush=True)
    finally:
        viz.stop()


if __name__ == "__main__":
    main()
