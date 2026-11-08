#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["anthropic>=0.80"]
# ///
"""Local-only proxy to the Anthropic API for testing web/api/*.js on your machine.

It authenticates the same way scripts/probar.py does (your `ant` login), so no API key
has to be copied anywhere. The token stays inside this process and is never printed.

  uv run --script scripts/dev-proxy.py            # listens on 127.0.0.1:8788
  ANTHROPIC_BASE_URL=http://127.0.0.1:8788 node scripts/dev-web.js
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import anthropic

client = anthropic.Anthropic()
PASS_HEADERS = ("anthropic-beta", "anthropic-version")


class Proxy(BaseHTTPRequestHandler):
    def _forward(self, method: str) -> None:
        parts = urlsplit(self.path)
        if not parts.path.startswith("/v1/sessions"):
            self.send_error(403, "only /v1/sessions is proxied")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else None
        headers = {h: self.headers[h] for h in PASS_HEADERS if self.headers.get(h)}
        # Keep the raw query in the path: SDK params must be a dict, and types[] repeats.
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        try:
            if method == "GET":
                data = client.get(target, cast_to=object, options={"headers": headers})
            else:
                data = client.post(target, cast_to=object, body=body, options={"headers": headers})
            status, payload = 200, data
        except Exception as err:  # noqa: BLE001 - always answer, never drop the socket
            if not isinstance(err, anthropic.APIStatusError):
                status, payload = 502, {"error": {"message": f"proxy: {type(err).__name__}: {err}"}}
                raw = json.dumps(payload).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            status, payload = err.status_code, (err.body if isinstance(err.body, dict) else {"error": {"message": str(err)}})
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        self._forward("GET")

    def do_POST(self) -> None:
        self._forward("POST")

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"proxy {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}\n")


if __name__ == "__main__":
    print("dev proxy on http://127.0.0.1:8788 (local tests only)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8788), Proxy).serve_forever()
