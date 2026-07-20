# Pending Live-Verify — next session

Three changes merged to `dev` 2026-06-10, Opus-verified (functional tests + diff review),
NOT yet live-verified by the user. Live confirmation requires a Monitor + Proxy restart — the
running monitor/proxy froze their code BEFORE these changes (proxy freezes a code snapshot at start).

## 1. Proxy-pane: numeric delta badges removed + dead no-turns fallback deleted

**Change:** removed the `Δsys`/`Δtools`/`Δmsgs:+Nk(~Mtok)` char-count badges at all three render
sites (collapsed REQ header + expanded sys/tools section deltas); deleted the provably-unreachable
no-turns fallback (`_render_entries_no_turns` + the whole `render_entry.py`, 225 LOC). `_format_delta`
removed; `_format_k` kept.

**Verify (monitor restart):**
- Collapsed request rows show NO `Δmsgs:...` badge.
- Expand a request → no `Δsys`/`Δtools` on the sys/tools detail lines.
- Message-list delta still works: expand shows only the NEW messages `[N]`, not all messages.
- `⚠S`/`⚠T` warnings still appear when sys/tools actually change; `🔧` tool-mod badge intact.

**Refs:** `src/proxy_display/{render_turn,render_sections,format}.py`; `src/proxy_display/DOCS.md`.

## 2. Format-drift detector (FORMAT WARNINGS) removed entirely

**Change:** removed the unknown-JSONL-type detection across constants (`KNOWN_*` sets),
`jsonl_extractors.detect_unknown_types`, the parser's `unknown_types` return value (10→9 tuple),
`warnings_parse.py` (deleted), and the FORMAT WARNINGS render block. TOOL ERRORS + `malformed_warnings`
kept. Rationale: detector was unreliable; format inspection now via the proxy pane (full forwarded
payload).

**Verify (monitor restart):**
- Warnings pane shows NO "FORMAT WARNINGS" section.
- TOOL ERRORS renders normally; no crash in the JSONL parse path.

**Refs:** `decisions/pipe03_core_loop.md` (IST-5 RETIRED); `src/jsonl/`, `src/panes/`, `src/core/`.

## 3. Inject-badge "." phantom fixed

**Change:** extended the empty-block-placeholder (`"."`) badge-skip to the system and tools-desc
sections (was message-path-only). A system pass stripping a block down to the `"."` placeholder no
longer phantom-badges as `inj`.

**Verify (PROXY restart — write-side change):**
- A request where a system block is stripped to `"."` (sys[3] via `_strip_sys3`, sys[2] when proxy
  rules are empty) shows NO `1inj`.
- A REAL proxy-rules injection into sys[2] (fires after an edit to `~/.claude/shared-rules/`) STILL
  badges `1inj` — that is a genuine inject, kept by design.
- bg-exit `"background done"` injects and whole-tool MCP injects still badge — unchanged.

**Refs:** `decisions/OldThemes/proxy_tool_stripping/17_badge_false_positives.md` (Source 4);
`src/proxy/strip_inject_delta.py`.

## Restart requirement

The proxy freezes a code copy at start; the monitor TUI runs from its launch-time code. #1 and #2 are
read-side (monitor restart). #3 is write-side in the proxy (proxy restart needed to stop writing the
phantom `"."` attribution into the `_injected` dual-log).
