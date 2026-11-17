#!/usr/bin/env python3
"""Local forwarding proxy: Libredesk AI -> Gemini (OpenAI-compatible endpoint).

Libredesk is configured with base URL http://localhost:18080 and a dummy
api_key placeholder. This proxy receives Libredesk's OpenAI-compatible
requests, drops the dummy Authorization header, and re-issues each request
to https://generativelanguage.googleapis.com/v1beta/openai with the stored
Gemini credential applied via the dynamic-credentials surrogate helper
(Sentinel/authd swaps the surrogate for the real key only on the approved
egress request to the registered host).

The real API key value is NEVER readable here: it never appears in this
file, in any log, in any command argument, or in the Libredesk config.
The surrogate header value is also never logged.

Allowed upstream paths: GET  /v1/models
                        POST /v1/chat/completions
                        POST /v1/embeddings
Libredesk appends "/chat/completions" and "/embeddings" to its base URL,
so it is configured with base URL http://localhost:18080/v1; the proxy
strips the /v1 prefix when forwarding upstream (the Gemini OpenAI
endpoint is .../v1beta/openai/chat/completions, with no /v1 segment).
Local only:             GET  /healthz  (proxy health, no upstream call)

Usage:  ./phase-4-proxy.sh start|stop|status
"""
import json
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request

HOST = "generativelanguage.googleapis.com"
UPSTREAM = f"https://{HOST}/v1beta/openai"
ALLOWED = {
    ("GET", "/v1/models"),
    ("POST", "/v1/chat/completions"),
    ("POST", "/v1/embeddings"),
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def log(*parts):
    # Log only method/path/status/latency. Never headers or bodies.
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), *parts, flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep our own minimal log lines

    def _send(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def _handle(self):
        started = time.time()
        path = self.path.split("?", 1)[0]
        if self.command == "GET" and path == "/healthz":
            self._send(200, b'{"ok":true}')
            return
        if (self.command, path) not in ALLOWED:
            self._send(404, b'{"error":"not found"}')
            log(self.command, path, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        # Build a fresh upstream request: copy only Content-Type, never the
        # incoming (dummy) Authorization header. Strip the /v1 prefix
        # Libredesk adds (its base URL ends in /v1); the Gemini endpoint
        # has no /v1 segment after /v1beta/openai.
        upstream_path = path[3:] if path.startswith("/v1/") else path
        req = urllib.request.Request(
            UPSTREAM + upstream_path,
            data=body if self.command == "POST" else None,
            method=self.command,
        )
        req.add_header("Content-Type", "application/json")
        try:
            add_surrogate_to_request(req, "custom.gemini", allowed_hosts=[HOST])
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as resp:
                out = resp.read()
                self._send(resp.status, out, resp.headers.get("Content-Type", "application/json"))
                log(self.command, path, resp.status, f"{len(out)}B",
                    f"{time.time() - started:.1f}s")
        except urllib.error.HTTPError as e:
            out = e.read()
            self._send(e.code, out, e.headers.get("Content-Type", "application/json"))
            log(self.command, path, e.code, f"{len(out)}B",
                f"{time.time() - started:.1f}s")
        except Exception as e:  # authd failure, network failure, redirect, ...
            log(self.command, path, "proxy-error", type(e).__name__)
            self._send(502, json.dumps({"error": "proxy upstream failed"}).encode())


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18080), Handler)
    print("gemini proxy listening on 127.0.0.1:18080", flush=True)
    server.serve_forever()
