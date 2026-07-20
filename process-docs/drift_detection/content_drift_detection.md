# Content-Drift Detection — SR-Marker × Location Coverage

**Scope:** knowledge preserved from a closed, deferred tracking task (2026-04-27).
**Trigger:** a live audit on 2026-04-19 found 24,282 system-reminder instances in `tool_result.content` that our strip logic didn't catch — a new inject location introduced by a CC update.
**Status:** NOT implemented as a live pane or dev script. This doc preserves the approach for the next time a CC upgrade introduces new SR markers or new injection locations.

---

## Problem

2026-04-19: a live audit (ad-hoc Python script against 6 recent proxy JSONLs) found 24,282 `<system-reminder>` instances that passed through the proxy strip. All sat in `tool_result.content` — an inject location the strip code did not recurse into at the time.

The existing schema-drift detector (companion doc in this area) checks only structural invariants: top-level keys, system-block count, types, tools completeness. It sees no content. Content drift — new SR-marker texts, new injection locations — sits on an orthogonal axis and is fundamentally not covered by the schema detector.

That means: a new CC version can embed SR blocks in a new message-content shape, and neither schema drift nor the existing strip functions fire. The payload reaches Claude unmodified.

## State (code as of 2026-04-21, commit e1a3b9a)

### Strip Logic — `src/proxy/strip_sr.py`

`_strip_system_reminders(content, enabled_templates)` operates on **all 4 known content shapes**:

| Shape | Code path |
|---|---|
| top-level string | `isinstance(content, str)` → `_apply_sr_strip(content, ...)` |
| list of text blocks | `btype == 'text'` → `_apply_sr_strip(block['text'], ...)` |
| `tool_result.content` string | `btype == 'tool_result'`, `isinstance(inner, str)` → `_apply_sr_strip(inner, ...)` |
| `tool_result.content` list of text sub-blocks | `btype == 'tool_result'`, `isinstance(inner, list)` → iterate sub-blocks, strip `type==text` entries |

The implementation in `_apply_sr_strip()` matches only **standalone SR blocks** (regex `(?m)^<system-reminder>...` — only blocks starting at line start). This prevents false positives on embedded code literals like `if "<system-reminder>" in text:`.

### Template Catalog — 10 Templates

```
task-tools-nag       → "The task tools haven't been used recently"          (full)
pyright-diagnostics  → "<new-diagnostics>"                                   (full)
deferred-tools       → "The following deferred tools are now available..."    (full)
user-interrupt       → "The user sent a new message while you were working:"  (partial — preserve user body)
system-notification  → "[SYSTEM NOTIFICATION - NOT USER INPUT]"              (full)
file-modified        → "Note: "                                               (full)
claudemd-contents    → ["As you answer the user's questions", "Contents of "] (full, but see below)
date-changed         → "The date has changed."                               (full)
skills-available     → "The following skills are available"                  (full)
plan-mode            → "Plan mode "                                          (full)
```

**Preserve guard:** SR blocks whose inner text begins with `"As you answer the user's questions, you can use the following context:"` are **not** stripped. That is the CLAUDE.md context block CC injects via SR — Opus needs this for project context, and `replaced_system_prompt` already replaces sys[2], so this SR block is the only remaining delivery path.

**mode 'partial' (user-interrupt):** removes only the IMPORTANT line, preserves the user body inside the SR wrapper.

### Replay Validation

Commit e1a3b9a: replay over **22 historical JSONLs** (~37k strip operations) — **0 false positives** (the predecessor greedy regex had ~970 FPs, including on embedded code literals in payloads).

### Schema Counterpart

Schema-drift detection (companion doc in this area) covers structural invariants (top-level key whitelist, system-block count, types). Content drift (which SR markers show up in which locations) is orthogonal — together the two detectors cover the full picture.

## Why Deferred

No CC update was in flight at the time. The acute leak was closed by e1a3b9a. Building a live pane or scanner script now would be premature:

- The KPI "stripped N / detected M" is meaningful only at CC-upgrade boundaries; in steady state it sits still at 100%
- Pane bandwidth is finite — a 24/7 drift pane for a rare event is the wrong resource allocation
- The manual one-shot audit (Step 1 below) takes 2-5 minutes and is fully sufficient for the upgrade case

Decision (2026-04-27): preserve the approach as a recipe here. When the next CC upgrade lands → run the procedure below. If the manual flow proves too costly across several upgrades → codify into dev scripts only then.

## Post-Upgrade Verification Procedure

When a new CC version arrives (auto-update or manual pin bump):

### Step 1 — Replay Scan Against New Logs (one-shot, no committed scaffolding)

Once the new CC version has produced ~10 sessions of proxy logs:

```python
# Iterate raw_payload.messages across recent JSONLs
# For each message, find ALL <system-reminder>...</system-reminder> occurrences
# Classify by location:
#   text_block            — top-level user-message text block (isinstance content str, or type==text in list)
#   tool_result_str       — string inside {type: tool_result, content: "..."}
#   tool_result_nested_text — {type: text, text: "..."} nested inside tool_result.content list
#   plain_string          — message.content is a plain string (not blocks)
# Count per (template_identifier × location)
# Surface any SR whose inner text does NOT match a known _SR_TEMPLATES identifier
```

Reference: the 2026-04-19 audit used exactly this scan pattern and found 24,282 bypasses in `tool_result_str` / `tool_result_nested_text` in under 2 minutes.

Expected coverage when the strip is complete: every SR location either matches a known template (= already handled) or shows up as an unknown template (= drift signal).

### Step 2 — Drift Triage

| Finding | Action |
|---|---|
| Known template, new location | Extend `_strip_system_reminders()` in `strip_sr.py` for the new content shape (the 2026-04-21 fix pattern) |
| Unknown template | CC introduced a new SR marker. Decide: strip-worthy (→ extend `_SR_TEMPLATES`) or pass-through? |
| No finding | Strip coverage is complete for this CC version. Done. |

### Step 3 — Optional: Codify Into dev Scripts

If several consecutive CC upgrades trigger this manual workflow, codify it in `dev/tool_use_analysis/`:

- `sr_scanner.py` — scans proxy JSONLs, counts SR per marker × location × session; output: MD report
- `sr_marker_discovery.py` — finds unknown SR texts via stem-matching against the known marker list, clusters similar ones

Report output: `YYYYMMDD_sr_content_drift.md` in `dev/tool_use_analysis/`.

These scripts were originally planned as part of the same closed tracking task. Not implemented because the manual one-shot audit (Step 1) suffices for the rare upgrade case.

## Why NOT a Live Pane

A live `src/drift_pane.py` analogous to `waste_pane` was originally planned alongside this work. Rejected 2026-04-27:

- Pane bandwidth is finite — drift detection is rare-event monitoring, not a 24/7 need
- The "stripped N / detected M" KPI is only meaningful at CC-upgrade boundaries; in steady state it sits still at 100%
- Window 2 (rules+hooks) gets deleted, not repurposed (separate session)

If the manual audit flow becomes too costly across multiple upgrades → escalate to a dev script (Step 3 above). A pane is the wrong shape for this problem.

## Files / Paths

- **Strip logic:** `src/proxy/strip_sr.py` — `_SR_TEMPLATES` catalog, `_strip_system_reminders()` with 4-shape coverage, `_PRESERVE_PREAMBLE` guard
- **Cache-pipeline evidence:** commit e1a3b9a, replay numbers (22 JSONLs, ~37k strips, 0 FP)

## Related

- Commit `e1a3b9a` (2026-04-21) — template-catalog SR strip with 4-content-shape coverage; standalone-SR regex; 10 templates
- A closed, deferred tracking task (2026-04-27) — knowledge preserved here
- A closed tracking task (2026-04-19) — schema-drift-detector parent work
- Companion topic: structural drift (top-level keys, system-block count, types)
