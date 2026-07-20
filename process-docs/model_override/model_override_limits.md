# Model Override — max_tokens and effort limits

## Original Concern

`_inject_model_override(payload, model_family)` (`src/proxy/inject_helpers.py`, values from `~/.claude/shared-rules/proxy_rules.json`) rewrote BOTH main (opus) and worker (sonnet) requests to `max_tokens: 128000`.

Two fears:
1. If the model's documented ceiling is below 128k — does the API 400, silently clamp, or silently fall back to a low default (DOWNGRADE vs what CC originally sent)?
2. Is `effort: high` the maximum settable for Sonnet 4.6, or can it go higher?

## Research

Source: `monitor-cc-reference` Anthropic docs.

### Per-model max output (synchronous Messages API)

| Model | Max output | Source |
|---|---|---|
| Opus 4.8 | 128,000 | `about_claude_models_overview.md` Max output row + `extended_thinking.md` |
| Sonnet 4.6 | 64,000 | `about_claude_models_overview.md` |
| Haiku 4.5 | 64,000 | `about_claude_models_overview.md` |

Note: 300k output is Batches-API-only via `output-300k-2026-03-24` beta.

### max_tokens over-limit behavior

`max_tokens` param schema (`api_messages_create.md`): `minimum: 0`, NO maximum enforced — "Different models have different maximum values for this parameter."

`stop_reason: "max_tokens"` documented as: "we exceeded the requested `max_tokens` **or the model's maximum**" (`api_messages_create.md`, `api_messages_batches_results.md`).

**Conclusion — API clamps to model ceiling.** Evidence chain: (1) schema enforces no max → no schema-400; (2) empirical — Sonnet workers ran with `max_tokens=128000`, zero 400s returned; (3) stop_reason references "the model's maximum" as a real server-side cap. Therefore Sonnet's 128000 was effectively 64k (clamped), NOT pinned to a low default. The "silent downgrade" fear is REFUTED.

Honest caveat: "clamp" is the necessary inference from stop_reason wording + no-400; the docs contain no literal "we clamp max_tokens" statement. Authoritative confirmation available via Models API `GET /v1/models/{id}` (not yet queried).

### Effort levels

Source: `monitor-cc-reference` `effort.md` Effort-levels table.

| Level | Notes |
|---|---|
| `low` | — |
| `medium` | Sonnet 4.6 recommended default |
| `high` | "exactly the same behavior as omitting the effort parameter" — the default |
| `xhigh` | Opus 4.8 / Opus 4.7 ONLY; not applicable to Sonnet |
| `max` | Sonnet 4.6 ceiling |

Effort parameter needs no beta header — "available on all supported models with no beta header required" (`effort.md`).

## Decisions

| Config | Old value | New value | Rationale |
|---|---|---|---|
| Worker (Sonnet 4.6) `max_tokens` | 128000 | **64000** | 128000 was harmless (clamped to 64k) but dishonest — config + proxy-pane displayed 128k that could never apply |
| Opus (Opus 4.8) `max_tokens` | 128000 | **128000** (keep) | Exact model ceiling |
| Worker (Sonnet 4.6) `effort` | `high` | **`high`** (keep) | Workers run investigations; `high` (the solid default) preferred over `medium`. `max` is available but not chosen |
| Opus (Opus 4.8) `effort` | `xhigh` | **`xhigh`** (keep) | Valid for Opus 4.8; `xhigh` must NOT be set on Sonnet (Opus-only) |

Change applied: `proxy_rules.json` `model_override_worker.max_tokens` set to 64000.

## Open

Models-API confirmation of clamp behavior — `GET /v1/models/{id}` not yet queried.
