from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks/portero_hook.py"
CATALOG = ROOT / "tests/fixtures/catalog.json"


def run_hook(event: dict, data_dir: Path) -> tuple[int, dict, str]:
    env = os.environ | {"PLUGIN_DATA": str(data_dir), "PORTERO_CATALOG_FIXTURE": str(CATALOG)}
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True, env=env)
    return proc.returncode, json.loads(proc.stdout or "{}"), proc.stderr


class HookIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.session = "session-a"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def event(self, name: str, **values):
        return {"hook_event_name": name, "session_id": self.session, **values}

    def enable(self) -> None:
        run_hook(self.event("SessionStart", source="startup"), self.data)
        run_hook(self.event("UserPromptSubmit", prompt="$portero on"), self.data)

    def test_new_session_resets_to_off(self) -> None:
        self.enable()
        run_hook(self.event("SessionStart", source="startup"), self.data)
        _, output, _ = run_hook(self.event("PreToolUse", tool_input={"message": "ordinary"}), self.data)
        self.assertEqual(output, {})

    def test_low_route_is_rewritten(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":["model-balanced"]}\nSay hello.'
        _, output, _ = run_hook(self.event("PreToolUse", tool_input={"message": marker}), self.data)
        hook = output["hookSpecificOutput"]
        self.assertEqual(hook["updatedInput"]["model"], "model-fast")
        self.assertEqual(hook["updatedInput"]["reasoning_effort"], "low")
        self.assertEqual(hook["updatedInput"]["message"], "Say hello.")

    def test_fork_resume_and_compact_preserve_parent_state(self) -> None:
        self.enable()
        for source in ("fork", "resume", "compact"):
            run_hook(self.event("SessionStart", source=source), self.data)
            _, output, _ = run_hook(self.event("UserPromptSubmit", prompt="$portero status"), self.data)
            self.assertIn("ON", output["hookSpecificOutput"]["additionalContext"])

    def test_heavy_route_is_denied_until_confirmation(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"critico","model":"model-deep","effort":"xhigh","fallbacks":["model-balanced"]}\nAudit.'
        _, denied, _ = run_hook(self.event("PreToolUse", turn_id="first", tool_input={"message": marker}), self.data)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        run_hook(self.event("UserPromptSubmit", turn_id="confirmed", prompt="sí"), self.data)
        _, allowed, _ = run_hook(self.event("PreToolUse", turn_id="confirmed", tool_input={"message": marker}), self.data)
        self.assertEqual(allowed["hookSpecificOutput"]["permissionDecision"], "allow")
        _, denied_again, _ = run_hook(self.event("PreToolUse", turn_id="confirmed", tool_input={"message": marker}), self.data)
        self.assertEqual(denied_again["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_heavy_approval_is_bound_to_exact_spawn_and_turn(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"critico","model":"model-deep","effort":"xhigh","fallbacks":[]}\nAudit.'
        other = marker.replace("Audit.", "Different task.")
        run_hook(self.event("PreToolUse", turn_id="one", tool_input={"message": marker}), self.data)
        run_hook(self.event("UserPromptSubmit", turn_id="two", prompt="yes"), self.data)
        _, denied, _ = run_hook(self.event("PreToolUse", turn_id="two", tool_input={"message": other}), self.data)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        run_hook(self.event("UserPromptSubmit", turn_id="three", prompt="yes"), self.data)
        _, wrong_turn, _ = run_hook(self.event("PreToolUse", turn_id="four", tool_input={"message": other}), self.data)
        self.assertEqual(wrong_turn["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_nonconfirmation_clears_heavy_request(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"critico","model":"model-deep","effort":"xhigh","fallbacks":[]}\nAudit.'
        run_hook(self.event("PreToolUse", turn_id="one", tool_input={"message": marker}), self.data)
        run_hook(self.event("UserPromptSubmit", turn_id="two", prompt="not now"), self.data)
        run_hook(self.event("UserPromptSubmit", turn_id="three", prompt="yes"), self.data)
        _, denied, _ = run_hook(self.event("PreToolUse", turn_id="three", tool_input={"message": marker}), self.data)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_missing_model_falls_back(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"missing","effort":"low","fallbacks":["model-fast"]}\nSay hello.'
        _, output, _ = run_hook(self.event("PreToolUse", tool_input={"message": marker}), self.data)
        self.assertEqual(output["hookSpecificOutput"]["updatedInput"]["model"], "model-fast")

    def test_parallel_post_uses_matching_tool_id(self) -> None:
        self.enable()
        fast = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nFast.'
        balanced = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-balanced","effort":"low","fallbacks":[]}\nBalanced.'
        run_hook(self.event("PreToolUse", turn_id="turn", tool_use_id="fast", tool_input={"message": fast}), self.data)
        run_hook(self.event("PreToolUse", turn_id="turn", tool_use_id="balanced", tool_input={"message": balanced}), self.data)
        run_hook(self.event("PostToolUse", turn_id="turn", tool_use_id="fast", tool_response="model unavailable"), self.data)
        run_hook(self.event("PostToolUse", turn_id="turn", tool_use_id="balanced", tool_response="done"), self.data)
        _, output, _ = run_hook(self.event("PreToolUse", turn_id="next", tool_input={"message": fast}), self.data)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("No compatible", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_unmatched_post_cannot_poison_model(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nTask.'
        run_hook(self.event("PreToolUse", turn_id="turn", tool_use_id="call", tool_input={"message": marker}), self.data)
        run_hook(self.event("PostToolUse", turn_id="wrong", tool_use_id="call", tool_response="model unavailable"), self.data)
        run_hook(self.event("PostToolUse", turn_id="turn", tool_use_id="unknown", tool_response="model unavailable"), self.data)
        run_hook(self.event("PostToolUse", turn_id="turn", tool_response="model unavailable"), self.data)
        _, output, _ = run_hook(self.event("PreToolUse", turn_id="next", tool_input={"message": marker}), self.data)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_spawn_override_uses_isolated_bounded_context(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nDo one bounded task.'
        _, output, _ = run_hook(self.event("PreToolUse", tool_name="spawn_agent", turn_id="one", tool_input={"message": marker, "fork_turns": "all"}), self.data)
        self.assertEqual(output["hookSpecificOutput"]["updatedInput"]["fork_turns"], "none")

    def test_tier_only_route_selects_model_and_effort_in_hook(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido"}\nReview this one function.'
        _, output, _ = run_hook(self.event("PreToolUse", tool_name="spawn_agent", turn_id="one", tool_input={"message": marker}), self.data)
        updated = output["hookSpecificOutput"]["updatedInput"]
        self.assertEqual((updated["model"], updated["reasoning_effort"]), ("gpt-6-luna", "low"))
        self.assertEqual(updated["fork_turns"], "none")

    def test_tier_only_heavy_route_still_needs_user_approval(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"critico"}\nAudit this risk.'
        _, denied, _ = run_hook(self.event("PreToolUse", turn_id="one", tool_input={"message": marker}), self.data)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        run_hook(self.event("UserPromptSubmit", turn_id="two", prompt="sí"), self.data)
        _, allowed, _ = run_hook(self.event("PreToolUse", turn_id="two", tool_input={"message": marker}), self.data)
        updated = allowed["hookSpecificOutput"]["updatedInput"]
        self.assertEqual((updated["model"], updated["reasoning_effort"]), ("gpt-6-astra", "xhigh"))

    def test_third_spawn_in_same_turn_is_denied(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nDo one bounded task.'
        event = self.event("PreToolUse", turn_id="one", tool_input={"message": marker})
        self.assertEqual(run_hook(event, self.data)[1]["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(run_hook(event, self.data)[1]["hookSpecificOutput"]["permissionDecision"], "allow")
        denied = run_hook(event, self.data)[1]["hookSpecificOutput"]
        self.assertEqual(denied["permissionDecision"], "deny")
        self.assertIn("budget", denied["permissionDecisionReason"].lower())

    def test_status_reports_attempts_without_prompts(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nPrivate task details.'
        run_hook(self.event("PreToolUse", turn_id="one", tool_input={"message": marker}), self.data)
        _, output, _ = run_hook(self.event("UserPromptSubmit", prompt="$portero status"), self.data)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("1 route", context)
        self.assertNotIn("Private task details", context)

    def test_parallel_writes_keep_all_inflight_routes(self) -> None:
        self.enable()
        marker = 'PORTERO_ROUTE_JSON: {"tier":"rapido","model":"model-fast","effort":"low","fallbacks":[]}\nTask.'
        def spawn(index: int):
            return run_hook(self.event("PreToolUse", turn_id=f"turn-{index}", tool_use_id=f"call-{index}", tool_input={"message": marker}), self.data)
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(spawn, range(24)))
        self.assertTrue(all(code == 0 and output["hookSpecificOutput"]["permissionDecision"] == "allow" for code, output, _ in results))
        files = list((self.data / "sessions").glob("*.json"))
        state = json.loads(files[0].read_text())
        self.assertEqual(len(state["inflight"]), 24)


if __name__ == "__main__":
    unittest.main()

