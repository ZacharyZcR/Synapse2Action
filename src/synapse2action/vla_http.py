from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.request import Request, urlopen

from .vla import DeterministicVLABackend


Transport = Callable[[str, dict[str, str], bytes, float], bytes]


def _urllib_transport(url: str, headers: dict[str, str], payload: bytes, timeout: float) -> bytes:
    request = Request(url, data=payload, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return response.read()


@dataclass(slots=True)
class HTTPVLABackend:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 30.0
    transport: Transport = _urllib_transport
    request_count: int = 0

    def reset(self, task_payload: bytes) -> None:
        self.request_count = 0
        self._post("reset", task_payload)

    def infer(self, observation_payload: bytes) -> bytes:
        return self._post("infer", observation_payload)

    def _post(self, operation: str, payload: bytes) -> bytes:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.transport(
            f"{self.base_url.rstrip('/')}/{operation}",
            headers,
            payload,
            self.timeout_seconds,
        )
        self.request_count += 1
        return response


@dataclass(slots=True)
class VLAHTTPRequest:
    operation: str
    payload: dict[str, object]


class EmbeddedVLAServer:
    def __init__(self) -> None:
        self.backend = DeterministicVLABackend()
        self.requests: list[VLAHTTPRequest] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, name="embedded-vla")

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def __enter__(self) -> EmbeddedVLAServer:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                operation = self.path.removeprefix("/v1/")
                if operation not in {"reset", "infer"} or self.path != f"/v1/{operation}":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body)
                    if not isinstance(payload, dict):
                        raise ValueError
                    owner.requests.append(VLAHTTPRequest(operation, payload))
                    response = owner._dispatch(operation, body)
                except (json.JSONDecodeError, ValueError):
                    self.send_error(400)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *_: object) -> None:
                return

        return Handler

    def _dispatch(self, operation: str, body: bytes) -> bytes:
        if operation == "reset":
            self.backend.reset(body)
            return b'{"ok":true}'
        return self.backend.infer(body)
