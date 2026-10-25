#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def send(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def receive(proc: subprocess.Popen[str], request_id: int, timeout: float = 8) -> dict[str, Any]:
    assert proc.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for key, _ in selector.select(max(0, deadline - time.monotonic())):
            line = key.fileobj.readline()
            if not line:
                break
            message = json.loads(line)
            if message.get("id") == request_id:
                return message
    raise TimeoutError(f"timed out waiting for response {request_id}")


def fetch() -> dict[str, Any]:
    proc = subprocess.Popen(["codex", "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=os.environ.copy())
    try:
        send(proc, {"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "codex_portero", "title": "Codex Portero", "version": "0.1.0"}}})
        initialized = receive(proc, 1)
        if "error" in initialized:
            raise RuntimeError(initialized["error"])
        send(proc, {"method": "initialized", "params": {}})
        send(proc, {"method": "model/list", "id": 2, "params": {"limit": 100, "includeHidden": False}})
        result = receive(proc, 2)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result.get("result", {})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def read_local_cache() -> dict[str, Any] | None:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    path = codex_home / "models_cache.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("models"), list) and payload["models"]:
            return payload
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Codex Portero's model catalog cache.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        catalog = read_local_cache() or fetch()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{args.output.name}.", dir=args.output.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(catalog, stream, ensure_ascii=False, indent=2)
            os.replace(name, args.output)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return 0
    except Exception as exc:
        sys.stderr.write(f"catalog refresh failed: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
