---
name: portero
description: "Trigger: $portero, automatic subagent routing. Enable, disable, or apply Portero model and reasoning selection in Codex."
license: MIT
metadata:
  author: "Kevin Fernandez"
  version: "0.1.0"
---

## Activation Contract

Use this skill for `$portero on`, `$portero off`, `$portero status`, and every task while Portero is enabled for the current session.

## Hard Rules

- Keep the current main model as orchestrator; route execution through one or more subagents.
- Before spawning, tell the user the task split and each proposed model, reasoning effort, and short reason.
- Select the lowest sufficient tier from [the routing policy](references/routing-policy.md).
- Use only models and efforts supplied by the session catalog context. Include ordered fallback models in the route marker.
- Ask for explicit user confirmation before any `xhigh` or `max` spawn. Never infer consent.
- If every compatible subagent route fails, complete the task with the main orchestrator and say so.

## Execution Contract

For every subagent message, prepend exactly one machine-readable line:

`PORTERO_ROUTE_JSON: {"tier":"rapido","model":"catalog-id","effort":"low","fallbacks":["next-id"]}`

Then write the normal subagent instructions. The hook removes the marker before delivery. Do not claim a model ran until the spawn succeeds.

## Output Contract

After all work finishes, summarize the actual subagents, models, efforts, fallbacks, and outcomes inline. Do not create a routing log file.
