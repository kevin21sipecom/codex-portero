# Portero routing policy

Choose by actual task difficulty and risk, not prompt length. Long input with a mechanical request can still be `rapido` or `normal`. Pick the lowest tier likely to finish correctly; do not raise the tier merely because of uncertainty. If an attempt fails a concrete acceptance check, escalate once within the turn budget.

| Tier | Intended work | Requested family order | Effort |
| --- | --- | --- | --- |
| `rapido` | Greetings, renames, formatting, direct extraction | Luna → Sol → Astra | `low` |
| `ligero` | Short explanations, focused lookup, trivial one-file edits | Luna → Sol → Astra | `low` |
| `basico` | Small bounded changes, simple scripts, common technical questions | Luna → Sol → Astra | `medium` |
| `normal` | Multi-step work with straightforward logic or code explanation | Sol → Astra | `low` |
| `profundo` | Features, debugging, tests, or non-trivial multi-file work | Sol → Astra | `medium` |
| `avanzado` | Hard reproduction, module design, or judgment-heavy review | Sol → Astra | `high` |
| `complejo` | Architecture, large refactors, systems design, optimization | Astra → Sol | `high` |
| `critico` | Security, production, migration, concurrency, costly reversals | Astra only | `xhigh`; confirmation required |
| `maximo` | Explicit maximum-depth or deep-research request | Astra only | `max`; confirmation required |

The hook matches these declared model families against the live catalog and requires the exact effort to be advertised. Unknown families or unknown effort support fail closed; use a legacy explicit route only after checking compatibility. These are quality/cost starting assumptions, not measured Codex five-hour quota weights. A successful hook rewrite is a requested route, not proof that the host ran it.

