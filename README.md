# Codex Portero

Codex Portero is a local plugin experiment that keeps the active Codex model as orchestrator and routes execution to catalog-compatible subagents. It is session-scoped and starts off on a new root session. Resume, compaction, and fork events do not reset the parent session's state.

## Isolated validation

Run `./scripts/test_isolated.sh`. The script creates a disposable `CODEX_HOME` under `.test-profile/`, installs the plugin from a local test marketplace through Codex CLI, and runs deterministic hook tests with a fake catalog. It does not alter the user's normal Codex configuration or the original Claude Mods harness. **This verifies packaging and hook logic, not runtime execution of plugin-bundled hooks.**

## Compatibility result

Codex CLI 0.159.3 loads the plugin in an isolated profile. Native custom slash registration is not a public plugin API, so Portero uses explicit skill invocation: `$portero on`, `$portero off`, and `$portero status`.

The portable root `plugin.json` explicitly declares `extensions.com.openai.hooks`. The `.codex-plugin/plugin.json` compatibility manifest retains `hooks` and `skills` for Codex versions that read legacy plugin components.

The deterministic harness validates session reset/preservation, routing rewrite, declared fallbacks, one-time heavy-effort confirmation bound to the exact spawn and turn, and parallel tool-call correlation. Per [OpenAI's plugin packaging documentation](https://developers.openai.com/plugins/build/plugins), plugin-bundled lifecycle hooks require a manually installed Codex desktop plugin, and installation alone does not trust its hooks. A Codex CLI isolated install or TUI session does not establish that these hooks run. The repository does not install the plugin in the normal Codex profile.

## Desktop acceptance check

This final runtime check needs a person with Codex desktop and a signed-in account:

1. Install Codex Portero from a local marketplace in Codex desktop. Review and trust its hook definition through `/hooks` if that control is available; installation alone is insufficient.
2. Open a **new root session** and invoke `$portero status`. Confirm that it reports **off**, showing that `SessionStart` initialized the session rather than carrying over a previous state.
3. Invoke `$portero on`, check `$portero status` again, and ask for one harmless subagent task. Confirm the subagent route reflects Portero's declared model/effort policy. Invoke `$portero off` and confirm status returns to **off**.

Do not paste credentials or private logs into the acceptance report. If the hook-trust control or a subagent route is unavailable, report that limit rather than treating skill discovery as a pass.

At session start, Portero reads Codex's current `models_cache.json` when available and otherwise queries `model/list`; its own cache expires weekly. Catalog membership is not treated as proof of entitlement, so a rejected model is marked failed and the next declared compatible fallback is attempted. Portero never silently chooses an undeclared catalog model. If hook events lack `turn_id`, heavy-route confirmation fails closed; if they lack `tool_use_id`, Portero cannot attribute a subsequent model failure and does not mark one.
