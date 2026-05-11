"""HTTP server for dashboard and API."""

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
"""HTTP server for dashboard and API."""

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
"""HTTP server for dashboard and API."""

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
"""HTTP server for dashboard and API."""

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
        self._static_dir = static_dir
        super().__init__(*args, directory=str(static_dir), **kwargs)

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: D401
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
        p = self.path.split("?", 1)[0]
        if p == "/api/state":
            self._write_json(200, self._viz.state.snapshot())
            return
        if p == "/api/capabilities":
            self._write_json(200, self._viz.capabilities())
            return
        if p in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        if p != "/api/run":
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
"""HTTP dashboard: UI, ``GET /api/state``, ``GET /api/capabilities``, ``POST /api/run``."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


def start_dashboard_server(
    viz: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """``viz`` must provide ``.state.snapshot()``, ``.submit_run(dict)``, ``.capabilities()``."""
    static_dir = Path(__file__).resolve().parent / "static"
    get_snapshot: Callable[[], dict] = viz.state.snapshot
    submit_run: Callable[[dict], dict] = viz.submit_run
    capabilities: Callable[[], dict] = viz.capabilities

    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path == "/api/state":
                data = json.dumps(get_snapshot()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/api/capabilities":
                data = json.dumps(capabilities()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/" or path == "/index.html":
                index = static_dir / "index.html"
                body = index.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith("/static/"):
                rel = path[len("/static/") :].lstrip("/")
                if ".." in rel or rel.startswith("/"):
                    self.send_error(404)
                    return
                f = static_dir / rel
                if not f.is_file():
                    self.send_error(404)
                    return
                body = f.read_bytes()
                ctype = "application/octet-stream"
                if f.suffix == ".js":
                    ctype = "text/javascript; charset=utf-8"
                elif f.suffix == ".css":
                    ctype = "text/css; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path != "/api/run":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(n) if n else b"{}"
                body = json.loads(raw.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                result = submit_run(body)
            except (json.JSONDecodeError, ValueError) as e:
                err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            out = json.dumps(result).encode("utf-8")
            code = 200 if result.get("ok") else 409
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    httpd = ThreadingHTTPServer((host, port), DashboardHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t
