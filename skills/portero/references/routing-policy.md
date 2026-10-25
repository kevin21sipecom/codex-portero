# Portero routing policy

Choose by actual task difficulty, not prompt length. Long input with a mechanical request can still be `rapido` or `normal`. Spending more than necessary is a routing failure; choose the lowest tier likely to finish correctly. When uncertain between adjacent non-heavy tiers, choose the higher one.

| Tier | Intended work | Preferred effort |
| --- | --- | --- |
| `rapido` | Greetings, renames, formatting, direct extraction | `low` |
| `ligero` | Short explanations, focused lookup, trivial one-file edits | `medium` |
| `basico` | Small bounded changes, simple scripts, common technical questions | `high` |
| `normal` | Multi-step work with straightforward logic or code explanation | `low` on a more capable catalog model |
| `profundo` | Features, debugging, tests, or non-trivial multi-file work | `medium` |
| `avanzado` | Hard reproduction, module design, or judgment-heavy review | `high` |
| `complejo` | Architecture, large refactors, systems design, optimization | `high` on a leading catalog model |
| `critico` | Security, production, migration, concurrency, costly reversals | `xhigh`; confirmation required |
| `maximo` | Explicit maximum-depth or deep-research request | `max`; confirmation required |

Model names are deliberately absent. Rank candidates from the live catalog information and the task's needs. The hook validates availability and supported effort.
