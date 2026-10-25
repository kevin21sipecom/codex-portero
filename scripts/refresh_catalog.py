#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from pathlib import Path
from typing import Any


def send(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def receive(proc: subprocess.Popen[str], request_id: int, timeout: float = 8) -> dict[str, Any]:
    assert proc.stdout is not None
    # One reader per process preserves buffered lines between RPC requests.
    # Windows selectors cannot monitor anonymous subprocess pipes.
    messages = getattr(proc, "_portero_messages", None)
    if messages is None:
        messages = queue.Queue()
        proc._portero_messages = messages

        def read_lines():
            try:
                for line in proc.stdout:
                    messages.put(json.loads(line))
            except Exception as exc:
                messages.put(exc)
            finally:
                messages.put(None)

        reader = threading.Thread(target=read_lines, daemon=True)
        proc._portero_reader = reader
        reader.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            message = messages.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty:
            break
        if message is None:
            raise EOFError("Codex app-server closed its output")
        if isinstance(message, Exception):
            raise message
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
    raise TimeoutError(f"timed out waiting for response {request_id}")


def fetch() -> dict[str, Any]:
    executable = shutil.which("codex")
    if executable is None:
        raise FileNotFoundError("Codex CLI is not on PATH")
    proc = subprocess.Popen([executable, "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=os.environ.copy())
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
            proc.wait(timeout=2)
        reader = getattr(proc, "_portero_reader", None)
        if reader is not None:
            reader.join(timeout=2)
        if proc.stdin is not None:
            proc.stdin.close()
        if proc.stdout is not None and (reader is None or not reader.is_alive()):
            proc.stdout.close()


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
