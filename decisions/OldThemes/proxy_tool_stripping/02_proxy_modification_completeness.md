# Proxy Modification Completeness — CC→Proxy→API Traceability

Investigation track (Frage 2 of the proxy investigation). Goal: for every modification the proxy makes
to a CC request, can we fully reconstruct what CC sent (CC→proxy) from the log alone? Where are the
gaps — modifications that strip/overwrite without recording the original? Status: pipeline mapped,
preliminary audit done (error-prone, see corrections), DEEP systematic investigation pending.

## The Monitor contract (user framing)

The Monitor must depict EVERYTHING CC→proxy and yellow-highlight everything the proxy strips and does
NOT forward to the API. The `api_requests_*.jsonl` is the SOLE source. To yellow-highlight a stripped
element, the log must contain the actual CONTENT of what was removed (the "original"). A modification
that changes the payload without storing the original = a place the Monitor cannot show = blind spot.

## Request modification pipeline (src/proxy/addon.py:89-132, in order)

1. `apply_modification_rules` (rules.py) — message strips + system passes:
   - `_apply_system_passes`: system[2] REPLACED → `original_system2_text` saved (this block IS the CC
     system prompt, contains "model ID is claude-opus-4-7"). system[3] stripped (session_guidance,
     git_status, worktree-normalize) — function returns ONLY original_system2_text, NOT block-3 original.
   - message strips → `stripped_msg_originals` / `stripped_msg_removed` / `stripped_msg_indices`.
   - many SR strips: deferred_tools_sr, skills_sr, task_tools_nag, all_sr, bg_completed, hook_error_prefix,
     user_interrupt_sr, replaced_task_notification, replaced_bg_completed_text.
2. `_extract_deferred_tool_names` → `deferred_tools_names`.
3. fixation capture/apply (`_capture_fixation` / `_apply_fixation`).
4. `_strip_unused_tools` → `stripped_N_unused_tools` + `stripped_unused_tools_names`.
5. `inject_mcp_tools` → `injected_mcp_tools`.
6. `_strip_tool_descriptions` → `stripped_tool_descs_N` + `stripped_tool_descs_originals`.
7. `_strip_sys3` → `stripped_sys3` + `stripped_sys3_original`.
8. `_strip_blocked_tool_references` (payload_helpers.py:87) — removes `tool_reference` items pointing to
   blocklisted tools from tool_result blocks. **UNLABELED** — no entry in `modifications`, no original.
9. `_inject_context_management` → `injected_context_management`.
10. `_inject_model_override` (inject_helpers.py:7) — overwrites `model`/`thinking`/`effort`/`max_tokens`
    with proxy_rules.json config. **Original `model` field NOT saved.** Forwarded model = claude-opus-4-8;
    CC requested claude-opus-4-7 (per /model UI + system-prompt text).

## Preliminary capture audit (ERROR-PRONE — to confirm in deep investigation)

| Modification | Original captured? | Notes |
|---|---|---|
| replaced_system_prompt | ✅ original_system2_text | contains model ID 4-7 → model inferable here |
| message strips (skills_sr, session_guidance in msgs) | ✅ stripped_msg_originals/removed | confirmed: skills/session text present |
| stripped_N_unused_tools | ✅ names only | |
| stripped_tool_descs_N | ✅ stripped_tool_descs_originals | |
| stripped_sys3 | ✅ stripped_sys3_original (no git markers) | |
| block-3 strips (git_status, session_guidance, worktree) | ❓ CONTRADICTION | _apply_system_passes returns no block-3 original; BUT Monitor displays [3]'s original incl. model ID (screenshot). RESOLVE. |
| injected_model_override | ❌ model FIELD original not saved | but model 4-7 visible via system-prompt original (soft) |
| _strip_blocked_tool_references | ❌ unlabeled + no original | removes only tool_reference pointers (trivial content) |

## Corrections logged (my ad-hoc conclusions were repeatedly premature)

- git_status: it FIRES (label present = removed git-status from system block 3). NOT "removed nothing".
- Model: NOT a hard blind spot. The requested model (claude-opus-4-7) is visible in the Monitor via the
  system-prompt original (`original_system2_text` text says "model ID is claude-opus-4-7"). Only the
  `model` API FIELD override is unlogged separately. Note inconsistency: forwarded `model` field =
  claude-opus-4-8 while forwarded system text still says 4-7.
- Block 3: user confirms via screenshot that [3]'s original IS shown [STRIPPED] in the Monitor — which
  contradicts my reading that block-3 original isn't saved. Likely an index mismatch (Monitor block
  index ↔ api system[] index) OR the display reconstructs from original_system2_text. MUST resolve.

## Open questions for the deep investigation

1. Resolve the block-3 contradiction: map Monitor system-block index ↔ api `system[]` index ↔ which
   original field feeds the display. Is system[3]'s pre-strip original actually recoverable?
2. Per-modification, definitively: is the original captured AND rendered yellow by the Monitor? (build
   a systematic per-request audit + cross-check against the parser/render display logic.)
3. Gap classification: (a) HARD blind spot (content removed, no capture, not inferable), (b) SOFT
   (inferable from another field), (c) UNLABELED/silent (modifies without a `modifications` entry),
   (d) TRIVIAL (only metadata pointers, no real content).
4. Is overriding the user's selected model even intended, and is the field-vs-text inconsistency a bug?

## Investigation plan (user-directed, 2026-06-02)

1. (this file) OldThemes updated.
2. Opus: deep systematic investigation via probe scripts — audit ALL modifications across MANY requests
   AND map the Monitor display reconstruction (src/proxy_display/parser.py + render_sections.py) to know
   what's actually shown vs. only stored.
3. Worker: SAME task independently, writes PERSISTENT scripts in `dev/proxy_audit/`, reports whether it
   finds anything additional (cross-model verification).
4. Deliverable: report with concrete examples + the gap classification above.
