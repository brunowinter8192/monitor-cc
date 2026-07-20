# bg_launch_ack Strip — FP-Nuke Fix (Anchor on Prefix), 2026-06-23

Sibling of a companion fix in this area — SAME class (over-broad strip replaces whole block content with `.`), DIFFERENT pass.

## Symptom
Live in-session: user `tool_result` blocks AND user-typed/pasted messages collapsed to `.` whenever the content contained the phrase `running in background with ID` ANYWHERE. Surfaced mid-session once RAG/Bash outputs about background/polling topics (which quote the marker) started flowing; a pasted copy of the strip source itself was nuked.

## Root cause — confirmed (masked source read + dual_log fn_map)
`src/proxy/strip_bg_launch_ack.py::_strip_bg_launch_ack`
- Marker `_BG_LAUNCH_ACK_MARKER = 'running in background with ID'`.
- Decision was `if _BG_LAUNCH_ACK_MARKER in <text>:` — substring ANYWHERE — then full block-content replacement with `.`.
- Applied across all 4 content shapes (str / list-text / tool_result-str / tool_result-list-text).
- Any legit block merely CONTAINING the phrase as data → entire block destroyed.

### Evidence (session 1782166807 dual_log `_stripped` fn_map + `_original`)
| msg | role | type | len | verdict |
|---|---|---|---|---|
| 39/62/79/90 | user | tool_result | 302 | genuine ack — starts `Command running in background with ID: <id>. Output is being written to: ...` |
| 122 | user | tool_result | 48600 | FP — rag-cli/collections output, marker mid-content → nuked |
| 124 | user | tool_result | 10040 | FP — bash chain output → nuked |
| 143 | user | str | 2508 | FP — paste of the strip source (contains marker literal) → nuked |

All FPs attributed to `_apply_bg_launch_ack_strip` via fn_map. The 4 genuine acks are all exactly 302 chars and all start with the same prefix; no FP starts with it (they start with `1\t=== collections`, `Exit code 1`, `# INFRASTRUCTURE`).

## Fix — committed `3ba9932` on dev
substring-anywhere → anchored `startswith`.
- Added `_BG_LAUNCH_ACK_PREFIX = 'Command running in background with ID:'` and `_is_bg_launch_ack(text) = text.lstrip().startswith(_BG_LAUNCH_ACK_PREFIX)`.
- All 4 shape-checks now use `_is_bg_launch_ack(...)`. Full-replace-to-`.` kept for genuine matches (their whole content IS the ack — correct to collapse).
- `_BG_LAUNCH_ACK_MARKER` retained for the `message_passes.py` fast-path guard import; the guard now only GATES whether the strip is called — the anchored decision lives in the strip.

## Verification
- Inline: genuine ack (str + tool_result) → `.`; 6063-char block w/ marker mid-content → unchanged; user-paste form → unchanged.
- Existing suite `dev/proxy_176_bg_launch_ack_tests.py` — 21 cases all PASS with the fix.

## Investigation constraint (meta — how to work around the live nuke)
The running proxy nukes any Read/RAG tool_result containing the marker. Workarounds used:
- Diagnosis via dual_log `fn_map` (marker-free fields: function name + element index) + `_original` content classification (lengths/bools only).
- Source read via masked Bash: `sed -E 's/[Bb]ackground/X/g' <file>`.
- Edits applied via Read-gate (Read returns `.` but satisfies the "has been read" gate) + exact ASCII `old_string`s matched against real disk bytes. tool_use inputs (Edit/Write/Bash command) are NOT stripped.

## Resolution (2026-06-23, post proxy-restart — all three Pending items closed)
Proxy restarted on the anchored fix (`3ba9932` merged to `main`; `dev == main`). All three deferred items done frictionlessly.

### 1. Live-verify — PASS (both directions)
- (a) Marker mid-content survives: `cat src/proxy/strip_bg_launch_ack.py` (source is full of the marker phrase) and RAG results quoting the marker both arrived INTACT — under the old substring-anywhere nuke the whole tool_result would have collapsed to `.`. dual_log of the live session (`api_requests_opus_monitor_cc_1782174574_stripped.jsonl`) shows NO `bg_launch_ack` fn_map entry for any of these blocks → the strip did not fire on them (preservation = absence of BL attribution).
- (b) Genuine ack still collapses: real CC ack from `1782166807_original.jsonl` opens `Command running in background with ID: bxab0pzvo. Output is being written to: /private/tmp/claude-...` (real ID, not the `<id>` doc placeholder) → starts exactly with `_BG_LAUNCH_ACK_PREFIX` → `_is_bg_launch_ack` True → collapses to `.`. (Note: the session harness returns background-command output directly instead of persisting the classic ack text in conversation history, so no fresh BL strip event could be forced through the live flow this session — verified instead against the real captured ack text + the anchored source logic.)

### 2. FP-regression — committed `4827e9c` (worker, TEST-ONLY)
4 new cases in `dev/proxy_176_bg_launch_ack_tests.py`, one per content shape, marker mid-content → preserved: `test_fp_tool_result_str_mid_content`, `test_fp_user_str_mid_content`, `test_fp_text_block_mid_content`, `test_fp_tool_result_list_mid_content`. Fixtures contain the marker substring (so the caller fast-path gate DOES fire) but none starts with the prefix → the anchored decision preserves them — exactly the bug class. Full suite now 26 checks, all PASS.

### 3. Current-state docs sync — done (orchestrator-written)
`src/proxy/DOCS.md` (pass-sequence inline + `strip_bg_launch_ack.py` Purpose) now describes the anchored `startswith` on `Command running in background with ID:` and the FP-fix rationale, replacing the old substring-anywhere wording. `_BG_LAUNCH_ACK_MARKER` documented as the caller-side fast-path gate only.
