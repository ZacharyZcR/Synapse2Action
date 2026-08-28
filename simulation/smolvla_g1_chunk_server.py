from __future__ import annotations

import argparse
from base64 import b64decode
from io import BytesIO
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from time import monotonic

import numpy as np
from PIL import Image
import torch

from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla import SmolVLAPolicy
from lerobot.policies.utils import prepare_observation_for_inference


class ChunkService:
    def __init__(self, model: Path) -> None:
        self.policy = SmolVLAPolicy.from_pretrained(model)
        self.policy.eval()
        self.preprocess, self.postprocess = make_pre_post_processors(
            self.policy.config,
            str(model),
            preprocessor_overrides={"device_processor": {"device": "cpu"}},
        )

    def infer(self, payload: dict[str, object]) -> dict[str, object]:
        state = np.asarray(payload["state"], dtype=np.float32)
        images = {
            f"observation.images.{name}": np.asarray(Image.open(BytesIO(b64decode(encoded))).convert("RGB"))
            for name, encoded in payload["images"].items()
        }
        observation = prepare_observation_for_inference(
            {"observation.state": state, **images},
            torch.device("cpu"),
            str(payload["task"]),
            "unitree_g1",
        )
        self.policy.reset()
        started = monotonic()
        actions = []
        with torch.inference_mode():
            for _ in range(self.policy.config.chunk_size):
                action = self.postprocess(self.policy.select_action(self.preprocess(observation)))
                actions.append(action.detach().cpu().numpy().reshape(-1).tolist())
        return {
            "session_id": payload["session_id"],
            "sequence": payload["sequence"],
            "actions": actions,
            "inference_ms": (monotonic() - started) * 1000,
        }


def handler(service: ChunkService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(200, {"ready": self.path == "/health"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/infer":
                self._send(404, {"error": "not found"})
                return
            try:
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self._send(200, service.infer(payload))
            except (KeyError, TypeError, ValueError) as exc:
                self._send(400, {"error": str(exc)})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Preloaded SmolVLA G1 action-chunk service")
    parser.add_argument("model", type=Path)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    service = ChunkService(args.model)
    HTTPServer((args.host, args.port), handler(service)).serve_forever()


if __name__ == "__main__":
    main()
