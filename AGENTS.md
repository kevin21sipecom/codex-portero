# Codex Portero agent instructions

- Keep the main Codex model as orchestrator; only subagents are routed.
- Preserve session-scoped opt-in and explicit confirmation for `xhigh` or `max`.
- Never hard-code product model names; validate against catalog fixtures or live catalog metadata.
- Keep hook scripts deterministic and dependency-free.

## CI hardening

This agent-bearing project uses the Zetter native bounded-review gate contract. Risk tiering selects the review lenses. Only post-apply may start a review; pre-commit, pre-push, pre-pr, and release run `gentle-ai review validate --gate <gate>` through `scripts/validate_gate.sh`. Review mode remains user-controlled and is not enabled by this repository.
