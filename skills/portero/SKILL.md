---
name: portero
description: "Trigger: $portero, automatic subagent routing. Enable, disable, or apply Portero model and reasoning selection in Codex."
license: MIT
metadata:
  author: "Kevin Fernandez"
  version: "0.2.2"
---

## Activation Contract

Use this skill for `$portero on`, `$portero off`, `$portero status`, and every task while Portero is enabled for the current session.

## Hard Rules

- Answer brief, self-contained requests that need no tools (such as a greeting or short translation) directly in the current main model. Do not spawn a subagent or announce a route for these requests.
- For substantial bounded work, keep the current main model as a thin orchestrator and delegate to one subagent when that is useful. Do not spawn merely to move a trivial answer to a cheaper model.
- When delegating, keep routing updates terse. Before the hook selects a route, tell the user only the bounded task being delegated; do not explain the rationale, list tiers or fallback models, or claim a model/effort prematurely.
- After the hook selects a route, surface exactly these three fields in one short line: `Task: <task> | Model: <requested model> | Reasoning: <requested effort>`. Do not add rationale, fallback lists, or other routing details. Label the model/effort as requested; do not imply runtime execution is confirmed.
- Portero does not change the selected main model. A delegated task still incurs main-model work; recommend selecting a lighter main model before submitting simple requests when the user wants to reduce that usage. Do not promise token or plan-quota savings from delegation.
- Select the lowest sufficient tier from [the routing policy](references/routing-policy.md).
- Use the tier-only marker so the hook selects a catalog-compatible model and effort from its declared family policy. Legacy explicit routes remain supported.
- Pass a self-contained objective, relevant paths, constraints, and acceptance checks. Do not copy the full conversation or repeat a completed investigation.
- For `spawn_agent`, use `fork_turns: "none"`; model and effort overrides cannot be combined with full-history inheritance on supported hosts.
- Use a second spawn only for a distinct independent task or a retry justified by a concrete failure. The hook limits accepted spawns to two per turn when a turn ID is available.
- Ask for explicit user confirmation before any `xhigh` or `max` spawn. Never infer consent.
- If every compatible subagent route fails, complete the task with the main orchestrator and say so.

## Execution Contract

Only when delegating, prepend exactly one machine-readable line to the subagent message:

`PORTERO_ROUTE_JSON: {"tier":"rapido"}`

Then write the bounded subagent instructions. The hook removes the marker and requests the model and effort. For older callers, an explicit `model`, `effort`, and ordered `fallbacks` are still accepted. Do not claim a model actually ran until runtime evidence confirms it.

## Output Contract

After delegated work finishes, summarize requested routes and outcomes inline. Direct responses need no route summary. Distinguish a hook's requested model/effort from runtime-confirmed execution. `$portero status` reports route attempts and model failures, not tokens or five-hour quota savings. Do not create a routing log file.

