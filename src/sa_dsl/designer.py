from __future__ import annotations

import hashlib
import html
import json
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


DEFAULT_ASSET_BASE = "https://gorundebug.com/mcp-ui/0.1.0"
DEFAULT_SNAPSHOT_TTL_SECONDS = 15 * 60
MAX_SNAPSHOTS = 32


def validate_asset_base(value: str) -> str:
    result = value.rstrip("/")
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Designer asset base must be an HTTPS URL without query or fragment")
    return result


def make_snapshot(project_name: str, canonical_yaml: str) -> dict[str, Any]:
    revision = f"sha256:{hashlib.sha256(canonical_yaml.encode('utf-8')).hexdigest()}"
    return {
        "schemaVersion": "1.0",
        "revision": revision,
        "mode": "read-only",
        "project": {"name": project_name},
        "canonicalYaml": canonical_yaml,
    }


def designer_document(
    asset_base: str = DEFAULT_ASSET_BASE,
    snapshot: dict[str, Any] | None = None,
) -> str:
    base = validate_asset_base(asset_base)
    snapshot_element = ""
    if snapshot is not None:
        serialized = json.dumps(snapshot, ensure_ascii=True, separators=(",", ":"))
        serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        snapshot_element = (
            '<script id="service-architect-snapshot" type="application/json">'
            f"{serialized}</script>"
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Service Architect</title>"
        f'<link rel="stylesheet" href="{html.escape(base)}/designer.css">'
        "</head><body style=\"margin:0;background:#07091a\">"
        f"{snapshot_element}<div id=\"service-architect-designer\"></div>"
        f'<script src="{html.escape(base)}/designer.js"></script>'
        "</body></html>"
    )


@dataclass(frozen=True, slots=True)
class _StoredSnapshot:
    value: dict[str, Any]
    expires_at: float


class DesignerSnapshotServer:
    def __init__(
        self,
        *,
        asset_base: str = DEFAULT_ASSET_BASE,
        ttl_seconds: int = DEFAULT_SNAPSHOT_TTL_SECONDS,
    ) -> None:
        self.asset_base = validate_asset_base(asset_base)
        self.ttl_seconds = ttl_seconds
        self._snapshots: dict[str, _StoredSnapshot] = {}
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                token = self.path.removeprefix("/designer/").split("?", 1)[0]
                snapshot = owner.get(token) if self.path.startswith("/designer/") else None
                if snapshot is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                body = designer_document(owner.asset_base, snapshot).encode("utf-8")
                asset_origin = urlparse(owner.asset_base)
                origin = f"{asset_origin.scheme}://{asset_origin.netloc}"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; "
                    f"script-src {origin}; style-src {origin} 'unsafe-inline'; font-src {origin}; "
                    "img-src data: blob:; connect-src 'none'; base-uri 'none'; "
                    "form-action 'none'; frame-ancestors 'self'",
                )
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def origin(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def publish(self, snapshot: dict[str, Any]) -> str:
        now = time.monotonic()
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._prune(now)
            while len(self._snapshots) >= MAX_SNAPSHOTS:
                oldest = min(self._snapshots, key=lambda key: self._snapshots[key].expires_at)
                del self._snapshots[oldest]
            self._snapshots[token] = _StoredSnapshot(snapshot, now + self.ttl_seconds)
        return f"{self.origin}/designer/{token}"

    def get(self, token: str) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            stored = self._snapshots.get(token)
            return stored.value if stored else None

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def _prune(self, now: float) -> None:
        expired = [key for key, value in self._snapshots.items() if value.expires_at <= now]
        for key in expired:
            del self._snapshots[key]
