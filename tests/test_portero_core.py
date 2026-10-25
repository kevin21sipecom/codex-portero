from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))

from portero_core import (  # noqa: E402
    HEAVY_EFFORTS,
    TIERS,
    Route,
    choose_compatible,
    extract_route,
    is_confirmation,
    normalize_command,
    parse_catalog,
)


class PorteroCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.models = parse_catalog(json.loads((ROOT / "tests/fixtures/catalog.json").read_text()))

    def test_nine_ordered_tiers_and_heavy_efforts(self) -> None:
        self.assertEqual(len(TIERS), 9)
        self.assertEqual(TIERS[0], "rapido")
        self.assertEqual(TIERS[-1], "maximo")
        self.assertEqual(HEAVY_EFFORTS, {"xhigh", "max"})

    def test_route_marker_is_removed(self) -> None:
        data = {"message": 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":["model-balanced"]}\nSay hello.'}
        route, clean = extract_route(data)
        self.assertEqual(route, Route("rapido", "model-fast", "low", ("model-balanced",)))
        self.assertEqual(clean["message"], "Say hello.")

    def test_fallback_skips_failed_or_incompatible_model(self) -> None:
        route = Route("critico", "missing", "xhigh", ("model-fast", "model-deep"))
        self.assertEqual(choose_compatible(route, self.models, set()), ("model-deep", "xhigh"))
        self.assertIsNone(choose_compatible(route, self.models, {"model-deep", "model-balanced"}))

    def test_catalog_default_is_not_undeclared_fallback(self) -> None:
        route = Route("rapido", "missing", "low", ())
        self.assertIsNone(choose_compatible(route, self.models, set()))

    def test_commands_and_confirmation(self) -> None:
        self.assertEqual(normalize_command("$portero on"), "on")
        self.assertEqual(normalize_command("$portero off"), "off")
        self.assertEqual(normalize_command("$portero status"), "status")
        self.assertTrue(is_confirmation("sí"))
        self.assertFalse(is_confirmation("maybe"))

    def test_local_codex_cache_shape(self) -> None:
        payload = {
            "models": [
                {
                    "slug": "dynamic-model",
                    "visibility": "list",
                    "default_reasoning_level": "medium",
                    "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}],
                },
                {"slug": "hidden-model", "visibility": "hide", "supported_reasoning_levels": [{"effort": "high"}]},
            ]
        }
        parsed = parse_catalog(payload)
        self.assertEqual([model.model for model in parsed], ["dynamic-model"])
        self.assertEqual(parsed[0].efforts, ("low", "medium"))


if __name__ == "__main__":
    unittest.main()
