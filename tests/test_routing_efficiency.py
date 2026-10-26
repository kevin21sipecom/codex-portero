from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))

from portero_core import ModelEntry, extract_route, select_for_tier  # noqa: E402


class RoutingEfficiencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.models = [
            ModelEntry("gpt-6-astra", ("low", "medium", "high", "xhigh", "max")),
            ModelEntry("gpt-6.1-sol", ("low", "medium", "high", "xhigh")),
            ModelEntry("gpt-6-luna", ("low", "medium", "high")),
        ]

    def test_tier_only_marker_keeps_bounded_handoff(self) -> None:
        route, clean = extract_route({"message": 'PORTERO_ROUTE_JSON: {"tier":"rapido"}\nCheck one file.'})
        self.assertEqual(route.tier, "rapido")
        self.assertIsNone(route.model)
        self.assertIsNone(route.effort)
        self.assertEqual(clean["message"], "Check one file.")

    def test_fast_route_prefers_efficient_family_regardless_of_catalog_order(self) -> None:
        self.assertEqual(select_for_tier("rapido", self.models, set()), ("gpt-6-luna", "low"))

    def test_harder_route_uses_sufficient_model_and_effort(self) -> None:
        self.assertEqual(select_for_tier("profundo", self.models, set()), ("gpt-6.1-sol", "medium"))
        self.assertEqual(select_for_tier("critico", self.models, set()), ("gpt-6-astra", "xhigh"))

    def test_failed_model_falls_back_to_next_declared_family(self) -> None:
        self.assertEqual(select_for_tier("rapido", self.models, {"gpt-6-luna"}), ("gpt-6.1-sol", "low"))

    def test_unknown_family_fails_closed_instead_of_guessing_cost(self) -> None:
        self.assertIsNone(select_for_tier("rapido", [ModelEntry("unknown-model", ("low",))], set()))

    def test_critical_route_does_not_silently_downgrade_model_family(self) -> None:
        self.assertIsNone(select_for_tier("critico", self.models, {"gpt-6-astra"}))


if __name__ == "__main__":
    unittest.main()

