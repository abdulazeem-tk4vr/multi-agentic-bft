"""Clean runtime HTTP server module."""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, viz: Any, static_dir: Path, **kwargs: Any) -> None:
        self._viz = viz
        super().__init__(*args, directory=str(static_dir), **kwargs)

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            self._write_json(200, self._viz.state.snapshot())
            return
        if path == "/api/capabilities":
            self._write_json(200, self._viz.capabilities())
            return
        if path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/cancel":
            out = self._viz.cancel_run()
            self._write_json(200 if out.get("ok") else 400, out)
            return
        if path != "/api/run":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n else b"{}"
            body = json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("body must be object")
        except (json.JSONDecodeError, ValueError):
            self._write_json(400, {"ok": False, "error": "invalid JSON body"})
            return
        out = self._viz.submit_run(body)
        self._write_json(200 if out.get("ok") else 400, out)


def start_dashboard_server(viz: Any, *, host: str, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    static_dir = Path(__file__).resolve().parent / "static"
    handler = partial(DashboardHandler, viz=viz, static_dir=static_dir)
    httpd = ThreadingHTTPServer((host, port), handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return httpd, th
