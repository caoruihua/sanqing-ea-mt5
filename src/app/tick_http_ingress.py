"""HTTP-based tick ingress implementation using only the Python standard library."""

from __future__ import annotations

import json
import threading
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.app.tick_ingress import TickIngress, TickWakeupPayload


class TickHttpIngress(TickIngress):
    """Localhost-only HTTP ingress with ordered wake-up delivery."""

    def __init__(self, host: str, port: int, symbol: str, queue_policy: str = "fifo") -> None:
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("TickHttpIngress only supports localhost binding")
        if queue_policy not in {"fifo", "latest-only"}:
            raise ValueError("TickHttpIngress queue_policy must be 'fifo' or 'latest-only'")
        self.host = host
        self.port = port
        self.symbol = symbol
        self.queue_policy = queue_policy
        self._condition = threading.Condition()
        self._pending_payloads: deque[TickWakeupPayload] = deque()
        self._running = False
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._last_accepted_sequence = -1
        self._last_accepted_time_msc = -1

    def start(self) -> None:
        if self._running:
            return

        ingress = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/tick":
                    self.send_error(HTTPStatus.NOT_FOUND, "Unsupported path")
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                try:
                    payload_dict = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self.send_error(HTTPStatus.BAD_REQUEST, "Malformed JSON payload")
                    return

                try:
                    payload = TickWakeupPayload(
                        symbol=payload_dict["symbol"],
                        closed_bar_time=payload_dict["closed_bar_time"],
                        time_msc=payload_dict["time_msc"],
                        bid=payload_dict["bid"],
                        ask=payload_dict["ask"],
                        sequence=payload_dict["sequence"],
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return

                if payload.symbol != ingress.symbol:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Unexpected symbol")
                    return

                with ingress._condition:
                    if payload.time_msc < ingress._last_accepted_time_msc:
                        self.send_error(HTTPStatus.CONFLICT, "Out-of-order payload timestamp")
                        return
                    if (
                        payload.time_msc == ingress._last_accepted_time_msc
                        and payload.sequence <= ingress._last_accepted_sequence
                    ):
                        self.send_error(HTTPStatus.CONFLICT, "Out-of-order or replayed sequence")
                        return

                    ingress._last_accepted_sequence = payload.sequence
                    ingress._last_accepted_time_msc = payload.time_msc
                    if ingress.queue_policy == "latest-only":
                        ingress._pending_payloads.clear()
                    ingress._pending_payloads.append(payload)
                    ingress._condition.notify()

                response = json.dumps({"accepted": True}).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        self._server = ThreadingHTTPServer((self.host, self.port), _Handler)
        self.port = int(self._server.server_address[1])
        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def wait(self) -> TickWakeupPayload | None:
        with self._condition:
            while self._running and not self._pending_payloads:
                self._condition.wait()

            if not self._running and not self._pending_payloads:
                return None

            return self._pending_payloads.popleft()

    def stop(self) -> None:
        with self._condition:
            self._running = False
            self._condition.notify_all()

        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
