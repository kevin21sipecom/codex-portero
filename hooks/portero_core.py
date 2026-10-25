from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TIERS = (
    "rapido",
    "ligero",
    "basico",
    "normal",
    "profundo",
    "avanzado",
    "complejo",
    "critico",
    "maximo",
)
HEAVY_EFFORTS = {"xhigh", "max"}
EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max", "ultra")
ROUTE_PREFIX = "PORTERO_ROUTE_JSON:"


@dataclass(frozen=True)
class ModelEntry:
    model: str
    efforts: tuple[str, ...]
    default_effort: str | None = None
    is_default: bool = False


@dataclass(frozen=True)
class Route:
    tier: str
    model: str
    effort: str
    fallbacks: tuple[str, ...]


def parse_catalog(payload: dict[str, Any]) -> list[ModelEntry]:
    raw_models = payload.get("data", payload.get("models", []))
    if not isinstance(raw_models, list):
        return []
    result: list[ModelEntry] = []
    for raw in raw_models:
        if not isinstance(raw, dict) or raw.get("hidden") is True or raw.get("visibility") == "hide":
            continue
        model = raw.get("model") or raw.get("id") or raw.get("slug")
        if not isinstance(model, str) or not model:
            continue
        raw_efforts = raw.get(
            "supportedReasoningEfforts",
            raw.get("supported_reasoning_efforts", raw.get("supported_reasoning_levels", raw.get("efforts", []))),
        )
        efforts: list[str] = []
        if isinstance(raw_efforts, list):
            for effort in raw_efforts:
                value = (effort.get("reasoningEffort") or effort.get("effort")) if isinstance(effort, dict) else effort
                if isinstance(value, str) and value in EFFORT_ORDER and value not in efforts:
                    efforts.append(value)
        default = raw.get("defaultReasoningEffort", raw.get("default_reasoning_effort", raw.get("default_reasoning_level")))
        if isinstance(default, str) and default in EFFORT_ORDER and default not in efforts:
            efforts.append(default)
        result.append(ModelEntry(model, tuple(efforts), default if isinstance(default, str) else None, bool(raw.get("isDefault", raw.get("is_default", False)))))
    return result


def catalog_summary(models: Iterable[ModelEntry]) -> str:
    entries = [f"{m.model}({','.join(m.efforts) or 'default'})" for m in models]
    return ", ".join(entries) if entries else "catalog unavailable"


def extract_route(tool_input: dict[str, Any]) -> tuple[Route | None, dict[str, Any]]:
    clean = dict(tool_input)
    message_key = next((key for key in ("message", "prompt", "instructions") if isinstance(clean.get(key), str)), None)
    if message_key is None:
        return None, clean
    lines = clean[message_key].splitlines()
    marker_index = next((i for i, line in enumerate(lines) if line.startswith(ROUTE_PREFIX)), None)
    if marker_index is None:
        return None, clean
    try:
        data = json.loads(lines[marker_index][len(ROUTE_PREFIX):].strip())
        tier = data["tier"]
        model = data["model"]
        effort = data["effort"]
        fallbacks = data.get("fallbacks", [])
        if tier not in TIERS or effort not in EFFORT_ORDER or not isinstance(model, str):
            return None, clean
        if not isinstance(fallbacks, list) or not all(isinstance(item, str) for item in fallbacks):
            return None, clean
        clean[message_key] = "\n".join(lines[:marker_index] + lines[marker_index + 1:]).lstrip()
        return Route(tier, model, effort, tuple(fallbacks)), clean
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, clean


def choose_compatible(route: Route, models: list[ModelEntry], failed: set[str]) -> tuple[str, str] | None:
    by_id = {entry.model: entry for entry in models}
    candidates = (route.model,) + route.fallbacks
    for candidate in candidates:
        entry = by_id.get(candidate)
        if entry is None or candidate in failed:
            continue
        if not entry.efforts or route.effort in entry.efforts:
            return candidate, route.effort
    return None


def normalize_command(prompt: str) -> str | None:
    match = re.match(r"^\s*(?:/|\$)portero(?:\s+(on|off|status))?\s*$", prompt, re.IGNORECASE)
    return (match.group(1) or "status").lower() if match else None


def is_confirmation(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    return normalized in {"yes", "y", "si", "sí", "confirm", "confirmo", "usar", "use it", "continue", "continuar"}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
