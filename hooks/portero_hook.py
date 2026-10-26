#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from portero_core import (
    HEAVY_EFFORTS,
    catalog_summary,
    choose_compatible,
    extract_route,
    is_confirmation,
    load_json,
    normalize_command,
    parse_catalog,
    save_json,
)


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False))


def state_path(event: dict[str, Any]) -> Path:
    data_root = Path(os.environ.get("PLUGIN_DATA", str(Path(tempfile.gettempdir()) / "codex-portero")))
    session = str(event.get("session_id") or "unknown")
    safe = hashlib.sha256(session.encode()).hexdigest()[:24]
    return data_root / "sessions" / f"{safe}.json"


def initial_state() -> dict[str, Any]:
    return {"enabled": False, "pending_heavy": None, "heavy_approval": None, "failed_models": [], "inflight": {}, "turn_budget": None, "stats": {"routes": 0, "model_failures": 0}}


@contextmanager
def session_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+b") as lock:
        if os.name == "nt":
            # Lock a fixed byte, including for a newly created empty file.
            deadline = time.monotonic() + 10
            while True:
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out acquiring Portero session lock")
                    time.sleep(0.02)
        else:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def route_fingerprint(tool_input: dict[str, Any]) -> str:
    payload = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def catalog_path() -> Path:
    fixture = os.environ.get("PORTERO_CATALOG_FIXTURE")
    if fixture:
        return Path(fixture)
    return Path(os.environ.get("PLUGIN_DATA", str(Path(tempfile.gettempdir()) / "codex-portero"))) / "catalog.json"


def refresh_catalog_if_stale() -> None:
    path = catalog_path()
    if os.environ.get("PORTERO_CATALOG_FIXTURE"):
        return
    if path.exists() and time.time() - path.stat().st_mtime < 7 * 24 * 60 * 60:
        return
    script = Path(__file__).resolve().parents[1] / "scripts" / "refresh_catalog.py"
    subprocess.run([sys.executable, str(script), "--output", str(path)], timeout=12, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def hook_output(event_name: str, **values: Any) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event_name, **values}}


def routing_context() -> str:
    return (
        "Portero is ON for this session. The main model is the orchestrator. "
        "Choose the lowest sufficient tier and delegate one bounded subagent by default. "
        "Use a self-contained prompt and PORTERO_ROUTE_JSON tier marker; Portero selects model and effort. "
        "Ask the user before xhigh or max. Do not duplicate a completed investigation."
    )


def handle(event: dict[str, Any]) -> None:
    if event.get("hook_event_name") == "SessionStart":
        refresh_catalog_if_stale()
    path = state_path(event)
    with session_lock(path):
        handle_locked(event, path)


def handle_locked(event: dict[str, Any], path: Path) -> None:
    event_name = str(event.get("hook_event_name") or "")
    state = load_json(path, initial_state())

    if event_name == "SessionStart":
        source = event.get("source")
        if source in ("startup", "clear"):
            state = initial_state()
            save_json(path, state)
        status = "ON" if state.get("enabled") else "OFF"
        context = routing_context() if state.get("enabled") else "Use $portero on to enable it."
        emit(hook_output(event_name, additionalContext=f"Portero is {status} for this session. {context}"))
        return

    models = parse_catalog(load_json(catalog_path(), {}))

    if event_name == "UserPromptSubmit":
        prompt = str(event.get("prompt") or "")
        command = normalize_command(prompt)
        if command == "on":
            state = initial_state() | {"enabled": True}
            save_json(path, state)
            emit(hook_output(event_name, additionalContext=f"Portero is now ON for this session. Confirm that to the user. {routing_context()}"))
            return
        if command == "off":
            state = initial_state()
            save_json(path, state)
            emit(hook_output(event_name, additionalContext="Portero is now OFF for this session. Confirm that to the user; do not delegate because of Portero."))
            return
        if command == "status":
            status = "ON" if state.get("enabled") else "OFF"
            stats = state.get("stats", {})
            emit(hook_output(event_name, additionalContext=f"Report Portero status as {status}. {stats.get('routes', 0)} route(s) requested, {stats.get('model_failures', 0)} model failure(s). These are not token or quota measurements. Catalog: {catalog_summary(models)}."))
            return
        if state.get("pending_heavy") and is_confirmation(prompt) and isinstance(event.get("turn_id"), str):
            state["heavy_approval"] = {"fingerprint": state["pending_heavy"]["fingerprint"], "turn_id": event["turn_id"]}
            state["pending_heavy"] = None
            save_json(path, state)
            emit(hook_output(event_name, additionalContext="The user explicitly approved the pending xhigh/max route once. Retry that exact spawn."))
            return
        if state.get("pending_heavy") or state.get("heavy_approval"):
            state["pending_heavy"] = None
            state["heavy_approval"] = None
            save_json(path, state)
        if state.get("enabled"):
            emit(hook_output(event_name, additionalContext=routing_context()))
        return

    if event_name == "PreToolUse" and state.get("enabled"):
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            emit(hook_output(event_name, permissionDecision="deny", permissionDecisionReason="Portero received an invalid subagent request."))
            return
        route, updated = extract_route(tool_input)
        if route is None:
            emit(hook_output(event_name, permissionDecision="deny", permissionDecisionReason="Portero requires a valid PORTERO_ROUTE_JSON line after announcing the route to the user."))
            return
        selected = choose_compatible(route, models, set(state.get("failed_models", [])))
        if selected is None:
            state["heavy_approval"] = None
            save_json(path, state)
            emit(hook_output(event_name, permissionDecision="deny", permissionDecisionReason="No compatible declared route remains. Continue with the main orchestrator and tell the user."))
            return
        model, effort = selected
        fingerprint = route_fingerprint(tool_input)
        approval = state.get("heavy_approval")
        approved = isinstance(approval, dict) and approval.get("fingerprint") == fingerprint and approval.get("turn_id") == event.get("turn_id") and isinstance(event.get("turn_id"), str)
        if effort in HEAVY_EFFORTS and not approved:
            state["heavy_approval"] = None
            state["pending_heavy"] = {"fingerprint": fingerprint, "turn_id": event.get("turn_id")}
            save_json(path, state)
            emit(hook_output(event_name, permissionDecision="deny", permissionDecisionReason=f"Ask the user to confirm {model}/{effort} before spawning. Do not infer consent."))
            return
        if effort not in HEAVY_EFFORTS and approval:
            state["heavy_approval"] = None
        if effort not in HEAVY_EFFORTS:
            state["pending_heavy"] = None
        turn_id = event.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            budget = state.get("turn_budget")
            if not isinstance(budget, dict) or budget.get("turn_id") != turn_id:
                budget = {"turn_id": turn_id, "count": 0}
            if budget["count"] >= 2:
                emit(hook_output(event_name, permissionDecision="deny", permissionDecisionReason="Portero's two-spawn turn budget is exhausted. Summarize current results or continue in a new turn."))
                return
            budget["count"] += 1
            state["turn_budget"] = budget
        updated["model"] = model
        if "model_reasoning_effort" in updated and "reasoning_effort" not in updated:
            updated["model_reasoning_effort"] = effort
        else:
            updated["reasoning_effort"] = effort
        if event.get("tool_name") == "spawn_agent" or "fork_turns" in updated:
            updated["fork_turns"] = "none"
        tool_use_id = event.get("tool_use_id")
        if isinstance(tool_use_id, str) and tool_use_id:
            state.setdefault("inflight", {})[tool_use_id] = {"model": model, "turn_id": event.get("turn_id")}
        state["heavy_approval"] = None
        state.setdefault("stats", {"routes": 0, "model_failures": 0})["routes"] += 1
        save_json(path, state)
        emit(hook_output(event_name, permissionDecision="allow", updatedInput=updated, systemMessage=f"Portero requested route: {route.tier} -> {model}/{effort}. Actual execution is not yet verified."))
        return

    if event_name == "PostToolUse" and state.get("enabled"):
        tool_use_id = event.get("tool_use_id")
        inflight = state.setdefault("inflight", {})
        route = inflight.get(tool_use_id) if isinstance(tool_use_id, str) else None
        if not isinstance(route, dict) or route.get("turn_id") != event.get("turn_id"):
            return
        inflight.pop(tool_use_id)
        if route is not None:
            save_json(path, state)
        response = event.get("tool_response")
        text = json.dumps(response, ensure_ascii=False).lower()
        failure_words = ("unavailable", "unsupported model", "model_not_found", "access denied", "not have access")
        if any(word in text for word in failure_words):
            failed = list(dict.fromkeys([*state.get("failed_models", []), route.get("model")]))
            state["failed_models"] = [item for item in failed if isinstance(item, str)]
            state.setdefault("stats", {"routes": 0, "model_failures": 0})["model_failures"] += 1
            save_json(path, state)
            emit({"decision": "block", "reason": "The selected model was unavailable. Retry the same bounded task with the next catalog-compatible fallback.", **hook_output(event_name, additionalContext="Portero recorded the failed model; retry the spawn so the next compatible fallback is selected.")})
        return


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("hook input must be an object")
        handle(event)
        return 0
    except Exception as exc:
        sys.stderr.write(f"codex-portero hook error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

