from __future__ import annotations

from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPSConnection
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlsplit

from .robot_transport import RobotTransport


HTTPTransport = Callable[[str, dict[str, str], bytes, float], bytes]


@dataclass(slots=True)
class PersistentHTTPTransport:
    connections: dict[tuple[str, str, int | None], HTTPConnection] = field(default_factory=dict)

    def __call__(self, url: str, headers: dict[str, str], payload: bytes, timeout: float) -> bytes:
        parsed = urlsplit(url)
        key = (parsed.scheme, parsed.hostname or "", parsed.port)
        connection = self.connections.get(key)
        if connection is None:
            connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
            connection = connection_type(parsed.hostname, parsed.port, timeout=timeout)
            self.connections[key] = connection
        connection.request("POST", parsed.path, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read()
        if response.status >= 400:
            raise ValueError(f"robot HTTP bridge returned {response.status}")
        return body

    def close(self) -> None:
        for connection in self.connections.values():
            connection.close()
        self.connections.clear()


@dataclass(slots=True)
class HTTPRobotTransport:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 5.0
    transport: HTTPTransport = field(default_factory=PersistentHTTPTransport)
    sensor_latency_ms: int = 0
    command_latency_ms: int = 0
    name: str = "http"
    command_request_count: int = 0
    observation_request_count: int = 0
    halt_count: int = 0

    @property
    def request_count(self) -> int:
        return self.command_request_count + self.observation_request_count

    def exchange(self, request: bytes) -> bytes:
        payload = json.loads(request)
        operation = payload.get("operation") if isinstance(payload, dict) else None
        if operation == "observe":
            self.observation_request_count += 1
        elif operation == "base_velocity":
            self.command_request_count += 1
        else:
            raise ValueError("unsupported robot HTTP exchange operation")
        return self._post("exchange", request)

    def halt(self) -> None:
        self._post("halt", b"{}")
        self.halt_count += 1

    def stop(self) -> None:
        self._post("stop", b"{}")

    def close(self) -> None:
        close = getattr(self.transport, "close", None)
        if close is not None:
            close()

    def _post(self, operation: str, payload: bytes) -> bytes:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self.transport(
            f"{self.base_url.rstrip('/')}/{operation}",
            headers,
            payload,
            self.timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class RobotHTTPRequest:
    operation: str
    payload: dict[str, object]


@dataclass(slots=True)
class EmbeddedRobotServer:
    bridge: RobotTransport
    requests: list[RobotHTTPRequest] = field(default_factory=list, init=False)
    _server: ThreadingHTTPServer = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)
    _ready: threading.Event = field(init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            name="embedded-robot",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            if not self._ready.wait(timeout=2):
                raise RuntimeError("embedded robot server did not start")
            self._started = True

    def _serve(self) -> None:
        self._ready.set()
        self._server.serve_forever()

    def close(self) -> None:
        if not self._started:
            self._server.server_close()
            return
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        self._started = False

    def __enter__(self) -> EmbeddedRobotServer:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                operation = self.path.removeprefix("/v1/")
                if operation not in {"exchange", "halt", "stop"} or self.path != f"/v1/{operation}":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body)
                    if not isinstance(payload, dict):
                        raise ValueError
                    owner.requests.append(RobotHTTPRequest(operation, payload))
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
        if operation == "exchange":
            return self.bridge.exchange(body)
        if operation == "halt":
            self.bridge.halt()
        else:
            self.bridge.stop()
        return b'{"ok":true}'
