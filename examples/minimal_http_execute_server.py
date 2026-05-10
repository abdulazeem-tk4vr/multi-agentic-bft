#!/usr/bin/env python3
"""Minimal POST /execute server for testing :func:`aegean.adapters.http_agents_from_endpoints`.

Run three terminals (different ports), then run the coordinator against them.

  python examples/minimal_http_execute_server.py 8081
  python examples/minimal_http_execute_server.py 8082
  python examples/minimal_http_execute_server.py 8083

The handler returns a fixed string; replace with your model/tool logic.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class ExecuteHandler(BaseHTTPRequestHandler):
    server_version = "AegeanMinimalWorker/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/execute":
            self.send_error(404, "POST only to /execute")
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            self.send_error(400, "invalid JSON")
            return

        task = payload.get("task")
        agent_id = payload.get("agent_id")
        phase = ((task or {}).get("context") or {}).get("aegean", {}).get("phase", "soln")

        # Replace this with real work (LLM, tools, etc.).
        out = f"worker-{self.server.server_port}:{phase}:{agent_id}"

        body = json.dumps(
            {
                "ok": True,
                "value": {"output": out, "metadata": {"confidence": 1.0, "tokens_used": 1}},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("port", type=int, help="Listen port (e.g. 8081)")
    args = p.parse_args()
    httpd = HTTPServer(("0.0.0.0", args.port), ExecuteHandler)
    print(f"listening on http://0.0.0.0:{args.port}/execute", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
