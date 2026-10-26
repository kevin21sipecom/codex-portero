---
name: portero
description: "Trigger: $portero, automatic subagent routing. Enable, disable, or apply Portero model and reasoning selection in Codex."
license: MIT
metadata:
  author: "Kevin Fernandez"
  version: "0.2.0"
---

## Activation Contract

Use this skill for `$portero on`, `$portero off`, `$portero status`, and every task while Portero is enabled for the current session.

## Hard Rules

- Keep the current main model as a thin orchestrator; delegate execution to one bounded subagent by default.
- Before spawning, tell the user the task split, selected tier, and short reason. Do not claim a model or effort until the hook requests it.
- Select the lowest sufficient tier from [the routing policy](references/routing-policy.md).
- Use the tier-only marker so the hook selects a catalog-compatible model and effort from its declared family policy. Legacy explicit routes remain supported.
- Pass a self-contained objective, relevant paths, constraints, and acceptance checks. Do not copy the full conversation or repeat a completed investigation.
- For `spawn_agent`, use `fork_turns: "none"`; model and effort overrides cannot be combined with full-history inheritance on supported hosts.
- Use a second spawn only for a distinct independent task or a retry justified by a concrete failure. The hook limits accepted spawns to two per turn when a turn ID is available.
- Ask for explicit user confirmation before any `xhigh` or `max` spawn. Never infer consent.
- If every compatible subagent route fails, complete the task with the main orchestrator and say so.

## Execution Contract

For every subagent message, prepend exactly one machine-readable line:

`PORTERO_ROUTE_JSON: {"tier":"rapido"}`

Then write the bounded subagent instructions. The hook removes the marker and requests the model and effort. For older callers, an explicit `model`, `effort`, and ordered `fallbacks` are still accepted. Do not claim a model actually ran until runtime evidence confirms it.

## Output Contract

After work finishes, summarize requested routes and outcomes inline. Distinguish a hook's requested model/effort from runtime-confirmed execution. `$portero status` reports route attempts and model failures, not tokens or five-hour quota savings. Do not create a routing log file.

