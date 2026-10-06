"""Local-only browser runner for the MIN0 CORE FORTH Python reference."""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "workbench"
VIEWER = ROOT / "viewer" / "live-viewer.html"
MAX_SOURCE_BYTES = 4096
MAX_REQUEST_BYTES = 8192

sys.path.insert(0, str(WORKBENCH))

from min0_core_forth_trace import TraceRecorder  # noqa: E402
from min0_core_forth_vm import signed  # noqa: E402
from min0_forth import make_host  # noqa: E402


def _signed_stack(values: list[int]) -> list[int]:
    return [signed(value) for value in values]


def execute_for_viewer(source: str) -> dict[str, Any]:
    if not isinstance(source, str):
        raise TypeError("source must be text")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} UTF-8 bytes")

    trace = TraceRecorder("python-live-viewer", include_source_words=True)
    outer = make_host(trace=trace)
    trace.events.clear()  # Startup vocabulary is trusted setup, not user execution.
    error = None
    try:
        outer.interpret(source)
    except Exception as exc:  # The API reports deterministic VM/compiler failures.
        error = {"name": type(exc).__name__, "message": str(exc)}

    words = []
    for event in trace.events:
        if event["event"] not in {"source.word.complete", "source.word.error"}:
            continue
        details = event["details"]
        state = event["state"]
        words.append(
            {
                "sequence": len(words) + 1,
                "token": details.get("token", "?"),
                "operands": details.get("operands", []),
                "action": details.get("action", event["event"]),
                "data_before": _signed_stack(details.get("data_stack_before", [])),
                "data_after": _signed_stack(state["data_stack"]),
                "return_stack": state["return_stack"],
                "loop_stack": state["loop_stack"],
                "steps": state["steps"],
            }
        )

    return {
        "ok": error is None,
        "terminal": outer.terminal_text,
        "data_stack": _signed_stack(outer.vm.data_stack),
        "return_stack": list(outer.vm.return_stack),
        "loop_stack": [
            {"limit": signed(frame.limit), "index": signed(frame.index)}
            for frame in outer.vm.loop_stack
        ],
        "steps": outer.vm.steps,
        "words": words,
        "error": error,
    }


class LiveViewerHandler(BaseHTTPRequestHandler):
    server_version = "MIN0LiveViewer/0.1"

    def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        raw = VIEWER.read_bytes()
        self._headers(HTTPStatus.OK, "text/html; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            if not self.headers.get("Content-Type", "").lower().startswith(
                "application/json"
            ):
                raise ValueError("Content-Type must be application/json")
            origin = self.headers.get("Origin")
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if origin is not None and origin != expected_origin:
                raise ValueError("cross-origin request is not allowed")
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request size is invalid")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = execute_for_viewer(payload.get("source"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": {"name": type(exc).__name__, "message": str(exc)}},
            )
            return
        self._send_json(HTTPStatus.OK, result)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {format % args}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the localhost MIN0 Live Viewer")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = HTTPServer(("127.0.0.1", args.port), LiveViewerHandler)
    print(f"MIN0 Live Viewer: http://127.0.0.1:{args.port}/")
    print("Localhost only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
