"""Local browser dashboard. Does not accept arbitrary commands."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps
from threading import Thread
from time import sleep
from urllib.parse import urlsplit
from html import escape
from .monitor import capture
from .settings import Settings


def page(data: dict[str, object]) -> str:
    processes = data.get("processes", {})
    unity = data.get("unity", {})
    found = processes.get("matches", []) if isinstance(processes, dict) else []
    proc_text = ", ".join(f'{x["name"]} (PID {x["pid"]})' for x in found) or "No tracked process detected"
    errs = unity.get("errors", 0) if isinstance(unity, dict) else 0
    warns = unity.get("warnings", 0) if isinstance(unity, dict) else 0
    recent = unity.get("recent", []) if isinstance(unity, dict) else []
    log_html = "\n".join(escape(str(line)) for line in recent) if recent else "Log excerpt disabled or unavailable"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="15"><title>APEX Companion</title><style>
    :root{{color-scheme:dark}}body{{font-family:system-ui,Segoe UI,sans-serif;background:#0b1118;color:#eaf3f5;margin:0;padding:36px;max-width:960px}}
    h1{{font-size:2.2rem;letter-spacing:-.06em}}h2{{font-size:1rem;color:#8eb8ba}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}.card{{padding:22px;background:#13202c;border:1px solid #254052;border-radius:18px}}.metric{{font-size:2rem;font-weight:700}}small{{color:#94abb5}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem;color:#bed3d5}}</style></head><body>
    <small>APEX / LOCAL DIAGNOSTICS / READ ONLY</small><h1>Desktop overview</h1><p>Updated {escape(str(data.get('timestamp_utc', 'unknown')))}</p>
    <div class="grid"><div class="card"><h2>Unity errors (recent log window)</h2><div class="metric">{int(errs)}</div></div><div class="card"><h2>Unity warnings (recent log window)</h2><div class="metric">{int(warns)}</div></div></div>
    <div class="card" style="margin-top:14px"><h2>Tracked processes</h2><p>{escape(proc_text)}</p></div>
    <div class="card" style="margin-top:14px"><h2>Unity log excerpt</h2><pre>{log_html}</pre></div>
    <small>Only binds to localhost. No external service is connected. Errors are approximate matches in the last 128 KiB, not unique build errors.</small></body></html>"""

def make_handler(settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            route = urlsplit(self.path).path
            if route not in ("/", "/health", "/api/status"):
                self.send_error(404)
                return
            if route == "/health":
                body, mime = b'{"status":"ok","scope":"localhost"}', "application/json"
            else:
                data = capture(settings)
                if route == "/api/status":
                    body, mime = dumps(data).encode(), "application/json"
                else:
                    body, mime = page(data).encode(), "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass
    return Handler

def serve(settings: Settings) -> None:
    with ThreadingHTTPServer((settings.bind_host, settings.port), make_handler(settings)) as server:
        print(f"APEX Companion running at http://{settings.bind_host}:{settings.port}/")
        print("Read-only and localhost-only. Ctrl+C to stop.")
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            pass
