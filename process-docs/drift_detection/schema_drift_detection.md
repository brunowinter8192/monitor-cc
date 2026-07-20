# Schema-Drift Detection — CC Version Regression Alert

**Scope:** session 2026-04-15 through 2026-04-19. A tracking task closed 2026-04-19.
**Trigger:** the first API request of every session (per model_family: opus + sonnet) validates the payload structure against a baseline. On drift → a warning in the Warnings pane under the "SCHEMA DRIFT" section.
**Next CC upgrade:** relevant again — see "Post-Upgrade Verification Procedure" below.

---

## Problem

New CC versions can silently change the payload structure. Proxy modifications (tools strip, system-reminder strip, rule injection, cache-marker placement) then break with no error signal. No detection mechanism existed.

## State (code as of 2026-04-19)

### Core Logic — `src/proxy/addon.py`

`_check_payload_schema(payload) -> list[str]` checks 5 invariants:

1. **Unknown top-level keys** — `set(payload.keys())` against a whitelist of known fields (model, max_tokens, system, messages, tools, stream, temperature, metadata, thinking, tool_choice, top_p, top_k, output_config, context_management, betas)
2. **System block count == 4** — `payload["system"]` must have exactly 4 blocks (CC convention: [0]=tiny cch-hash, [1]=misc, [2]=rules, [3]=gitStatus)
3. **system[2].type == "text"** — our rules block is text-typed
4. **messages[0].content is a list** — not str
5. **tools not empty** — CC always sends >= 1 tool

Additionally: **unknown keys in tools[0]** — against a tool-def whitelist (name, description, input_schema, cache_control, type, max_uses, allowed_domains, blocked_domains, etc.)

### Gate — `ProxyAddon._schema_checked: Dict[str, bool]`

The check runs **once per model_family per proxy instance**. `_schema_checked` is a dict (not a bool) since commit cc92feb → both Opus + Sonnet checked, Haiku excluded.

### Drift Signal — Warnings Pane

The warnings array is written as a proxy-log entry with `type: schema_warning`. `src/warnings_pane.py` parses these entries and renders them under the "SCHEMA DRIFT" section.

### Baseline — established empirically against CC v2.1.114

ZERO schema_warnings in the code at the time on the then-current CC version = silent pass = the baseline holds.

## Deliverables (D1-D5, all committed dev→main)

| D | Commit | What |
|---|---|---|
| D1 | ef86be8 | Session-scope fix: reset parse_proxy_log + schema_warnings on project-filter switch (previously global-persistent) |
| D2 | 6396eb7 | is_error structural detection (replaces substring match, removed 15 false positives) — indirectly benefits schema quality |
| D3 | 6f1901d | Scroll-direction fix in the Warnings pane (button 64 = wheel-up = offset decrement) |
| D4 | 42f5105 | Mutation test (dev/proxy/test_schema_check.py): 6 drift-injection cases, 6/6 PASS → the detector fires on real drift |
| D5 | cc92feb | Sonnet coverage: `_schema_checked` changed to Dict[str, bool] per model_family |

## Post-Upgrade Verification Procedure (IMPORTANT on the next CC update)

When auto-update or a manual pin bump moves to a new CC version:

### Step 1 — Natural Check (passive)
After a Monitor restart on the new CC version: open the Warnings pane, watch the "SCHEMA DRIFT" section on the first Opus request + first Sonnet request (worker spawn). Silent = the baseline still holds, the new version is structurally compatible.

### Step 2 — If Drift Warnings Appear
Read the output — which invariant was violated? Decision tree:

- **"Unknown top-level keys: X"** → CC is sending a new field. Extend the whitelist in `_check_payload_schema` (addon.py). Check whether the field is proxy-relevant (e.g. a new cache_control variant, a new context_management field).
- **"system has N blocks"** → a CC structure change. Critical. Check whether our sys[2] rules injection still works. May need to adjust the sys-marker logic in cache.py.
- **"system[2].type=image"** → CC has reorganized the system layout. Fix: recalibrate sys-block detection, adjust the rules-injection target.
- **"messages[0].content is str"** → the CC message format changed. Check the rule chain (content_strip.py) for list assumptions.
- **"tools is empty"** → CC sends no tools in the first request. Very unusual, a structural change. A full check is needed.
- **"Unknown keys in tools[0]"** → CC extended the tool-definition format. Update the whitelist in addon.py.

### Step 3 — Re-Run the Regression Test
```bash
./venv/bin/python dev/proxy/test_schema_check.py
```
Should stay 6/6 PASS even after baseline updates. If a case is hard-coded against the old CC structure (e.g. system block count) → update the test alongside the code baseline.

### Step 4 — Manual Drift Induction (optional, for confidence)
If the natural check is silent but the upgrade was large: fire a mock payload with artificial drift against `_check_payload_schema()`:
```python
from src.proxy.addon import _check_payload_schema
payload = {"model": "claude-opus-X", "extra_new_field": "xxx", ...}
print(_check_payload_schema(payload))
```
Expectation: at least the warning "Unknown top-level keys: ['extra_new_field']". Proves the detector runs in the new CC environment.

## Files / Paths

- **Core:** `src/proxy/addon.py` — `_check_payload_schema()`, `ProxyAddon._schema_checked`
- **Mutation test:** `dev/proxy/test_schema_check.py` — 6 cases
- **Warnings pane:** `src/warnings_pane.py` — SCHEMA DRIFT section, `schema_warnings` list
- **Baseline reference:** CC v2.1.114 (tested 2026-04-18, silent pass)

## Open Questions for a Future Upgrade

- The detector is one-shot per proxy session. A mid-session CC update would stay silent (unrealistic with a pinned version, but worth noting).
- The Sonnet schema check runs AFTER the override by inject_helpers — the check sees the modified payload, not what CC originally sent. On upgrade-related drift directly in CC's output, our override mutation could mask it. If this ever becomes relevant: move the check before `apply_modification_rules`.

## Related

- Commit `671ca54` — initial detector deploy
- A closed tracking task (2026-04-19)
- Shared rules: none specific, purely a project state doc
- Companion topic: content-side drift (SR marker × location × frequency)
