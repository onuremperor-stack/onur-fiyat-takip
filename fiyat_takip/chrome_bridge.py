import asyncio
import json
import queue
import threading
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HELPER_HEADER = "X-Onur-Helper"
MAX_RESULT_BYTES = 2_000_000


@dataclass(slots=True)
class _PendingJob:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None


class ChromeBridge:
    """Local-only job bridge used by the Onur Fiyat Takip Chrome extension."""

    def __init__(self, port: int = 8765) -> None:
        self.port = port
        self._jobs: queue.Queue[dict[str, str]] = queue.Queue()
        self._pending: dict[str, _PendingJob] = {}
        self._lock = threading.Lock()
        self._client_seen = threading.Event()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def _authorized(self) -> bool:
                return (
                    self.client_address[0] in {"127.0.0.1", "::1"}
                    and self.headers.get(HELPER_HEADER) == "1"
                )

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                if not self._authorized():
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                    return
                bridge._client_seen.set()
                if self.path == "/health":
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return
                if self.path == "/next":
                    try:
                        job = bridge._jobs.get_nowait()
                    except queue.Empty:
                        self.send_response(HTTPStatus.NO_CONTENT)
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        return
                    self._send_json(HTTPStatus.OK, job)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                if not self._authorized():
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                    return
                bridge._client_seen.set()
                if self.path != "/result":
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_RESULT_BYTES:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid body"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    job_id = str(payload["id"])
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
                    return
                with bridge._lock:
                    pending = bridge._pending.get(job_id)
                    if pending is not None:
                        pending.result = payload
                        pending.event.set()
                self._send_json(HTTPStatus.OK, {"ok": pending is not None})

            def log_message(self, _format: str, *_args: object) -> None:
                return

        class LocalServer(ThreadingHTTPServer):
            allow_reuse_address = True

        self._server = LocalServer(("127.0.0.1", self.port), Handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="onur-chrome-bridge",
            daemon=True,
        )
        self._thread.start()

    async def wait_for_client(self, timeout: float) -> bool:
        return await asyncio.to_thread(self._client_seen.wait, timeout)

    async def request(
        self,
        source: str,
        url: str,
        timeout: float,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        pending = _PendingJob()
        with self._lock:
            self._pending[job_id] = pending
        self._jobs.put({"id": job_id, "source": source, "url": url})
        completed = await asyncio.to_thread(pending.event.wait, timeout)
        with self._lock:
            self._pending.pop(job_id, None)
        if not completed or pending.result is None:
            raise TimeoutError(f"{source} için Chrome yardımcısı zaman aşımına uğradı")
        return pending.result

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self) -> "ChromeBridge":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
