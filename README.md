# Codex Portero

Codex Portero is a local plugin experiment that keeps the active Codex model as orchestrator and routes suitable work to catalog-compatible subagents. It is session-scoped and starts off on a new root session. Resume, compaction, and fork events do not reset the parent session's state.

## Conditional delegation (0.2.2)

With Portero enabled, brief self-contained requests that need no tools, such as a greeting or short translation, should be answered directly without a subagent or routing announcement. Substantial bounded work may still be delegated using the lowest sufficient tier; a longer mechanical transformation can be a reasonable Luna task. These are routing instructions, not a deterministic prompt classifier or a guarantee of token or plan-quota savings. The selected main model still receives the prompt and is not changed by Portero.

To avoid using a heavier main model for simple requests, select an available lighter model before sending the prompt: use the model picker in the Codex desktop app, `/model` in an interactive CLI session, or start a new CLI session with `codex -m gpt-6-luna`. Switch back to Sol when the main task needs stronger orchestration. Model availability depends on the client and account.

## Bounded routing (0.2.0)

Portero now accepts a tier-only `PORTERO_ROUTE_JSON` marker and chooses a declared
model family and reasoning effort from the live catalog. The policy for delegated work is in
`skills/portero/references/routing-policy.md`; older explicit model/effort
markers still work. The main model remains the orchestrator and is not changed
by the plugin. Supported `spawn_agent` calls use an isolated, self-contained
handoff (`fork_turns: none`) so a model override does not inherit the entire
conversation. When Codex supplies a turn ID, Portero allows two subagent spawns
per turn; additional work requires a new turn. Heavy routes still need explicit
confirmation. `$portero status` reports attempted routes and model failures,
without storing prompt text or claiming to measure tokens or plan quota.

Before claiming savings, compare equivalent tasks with Portero on and off:
record completion quality, retry counts, and the change in the same Codex
five-hour usage window. The hook reports a requested model/effort, not proof
of execution. Desktop acceptance must inspect the actual routed subagent and
confirm the hook is trusted; CLI and unit tests alone cannot prove either.

## Windows adaptation (0.1.1)

This local build adds Windows byte-range session locking and portable threaded
JSON-line reads for the catalog fallback. Unix retains `fcntl.flock`.
It requires Python 3.10+ available as `python3` and Codex CLI on PATH.
Check `python3 --version` before installation. No additional Python packages are needed.

The supplied local marketplace uses the adapted files, not the GitHub source.
From the extracted `codex-portero-windows` marketplace folder, run:

```powershell
codex plugin marketplace add .
codex plugin add codex-portero@portero-windows-local --json
```

Restart Codex desktop, review/trust its hooks using the desktop controls, and
start a new chat. Run `$portero status`; it must report OFF before opting in.
Do not bypass hook trust. Unit tests and CLI installation do not establish
that desktop lifecycle hooks run or that a routed model is available.

Run the portable test suite from the plugin folder:

```powershell
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Original upstream install (does not install this adaptation)

Add the GitHub marketplace and install the plugin:

```bash
codex plugin marketplace add kevin21sipecom/codex-portero
codex plugin add codex-portero@codex-portero
```

Restart the Codex desktop app, start a new conversation, and run `$portero status`. It should report **off**. Use `$portero on` to enable routing for that session; use `$portero off` to disable it. The marketplace is hosted in this repository and is separate from the public Plugin Directory.

Portero bundles lifecycle hooks. Install and verify it in Codex desktop to use the full routing behavior; CLI discovery or installation alone does not prove that the plugin's hooks are running. See [Desktop acceptance check](#desktop-acceptance-check) below.

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
