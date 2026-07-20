# Strip/Inject Span-Diff — Original↔Forwarded (Step 2+3 Verification)

Build step 2026-06-02. Pure dev/ analysis — no src/ change, no monitor change.
Verified against the fresh pair `api_requests_opus_monitor_cc_1780442876`.

## Core Finding: One Diff, Both Colors

Strip highlighting (yellow) and inject highlighting (green) come from the SAME diff:
original↔forwarded. Delete spans = stripped (yellow), insert spans = injected (green).
A block-level comparison (`original_block vs forwarded_block`) would not have been enough — sys[2]
e.g. **strips** the CC prompt AND **injects** the rules in the same block. Only the
text-span diff within an aligned block pair separates strip from inject cleanly.

## Alignment Strategy

- **system:** by index. An extra orig index = fully stripped; an extra fwd index = fully injected.
- **tools:** by name. Only-in-orig = the tool fully stripped; only-in-fwd = the tool fully injected;
  in-both = description/schema span-diffed.
- **messages:** by index (outer). Within-message (when content is a list on both sides): by block
  position (inner). Extra-orig-block = stripped; extra-fwd-block = injected.

## difflib Granularity

**Word-level when `SequenceMatcher.ratio() >= 0.1`** (real partial edits, e.g. a cache_control suffix
appended to a 55k base64-image block — ratio ≈ 1.0, only the last words change).

**Two-span full replacement when `ratio < 0.1`** (one stripped span + one injected span for the
whole block). Rationale: sys[2] has ratio ≈ 0.0038 (CC prompt vs rules — no shared text that would be
content-relevant). Word-level would produce thousands of meaningless individual-word spans.
Independent verification (Opus spot-check): ratio 0.0038 confirmed + identity of the stripped text
(CC prompt) and injected text (rules) confirmed.

## Verification Results on Pair 1780442876 (8 Requests, 2 Haiku + 6 Opus)

**sys[2] (REPLACED, ratio≈0.0038):**
- stripped: -7471 chars — `\nYou are an interactive agent that helps users with software engineering tasks…`
- injected: +130375 chars — `# Communication\n\nTwo principles for chat with the user: **drive** and **be honest**…`

**sys[3] (REPLACED):**
- stripped: -5511 chars — the CC CLAUDE.md/gitStatus block
- injected: +1 char — `"."` (proxy replacement)

**Haiku sys[2] (REPLACED):** same treatment — the title-generation prompt (-1159c) → `"."` (+1c).

**model (OVERRIDE, every opus request):** `claude-opus-4-7` → `claude-opus-4-8` visible as a field diff.

**tools:** 4 fully stripped (Agent, AskUserQuestion, ScheduleWakeup, ToolSearch);
5 descriptions reduced to "" (Bash -10665c, Edit -1094c, Read -1782c, Skill -1315c, Write -618c).
No injected MCP tools in this session.

**msg[0] per request (3 SR blocks → placeholders):**
- block[0]: SR deferred-tools (-599c) → `"."` (+1c)
- block[1]: SR skills (-5777c) → `"."` (+1c)
- block[2]: SR env-context (-373c) → `"\n"` (+1c)
- block[3]: user text IDENTICAL

**REQ#5+ msg[4] (hook-error-prefix strip detected):**
- stripped: the `"PreToolUse:Read hook error: [python3 …]:` prefix — correctly isolated as a strip span
- injected: the clean PDF path

**REQ#8 msg[8] block[4] (55k base64 image, ratio≈1.0 → word-level):**
Four preceding blocks IDENTICAL (130359c, 194243c, 204439c, 204439c).
Word-level diff correctly isolates only the cache_control JSON suffix as changed
(`false}` → `false, "cache_control": {"type": "ephemeral", "ttl": "1h"}}`).
Word-level carries here: ratio ~1.0, a single word change at the end — no block replace.

**Span counts per opus request:** sys -2/+2 | tools -9/+0 | msgs -3…-9/+3…+9 (grows with new turns).

## Tool

`dev/proxy_dual_log/diff_strip_inject.py` — pure analysis, read-only.
Reconstruction: inlines the verify_delta.py chain logic (self-contained, no import).
Matching: by request_id; fallback chain-order by model_family.

## Outlook

This engine (ratio threshold + block alignment + span classification) is the foundation for
green/yellow in the monitor's proxy pane: strip_vocab.py + proxy_display already know which
modifications occurred (`modifications[]` in the log entry) — the span diff now delivers
the TEXT coordinates for the coloring. Next iteration: the monitor read-side consumes
`_original` as the base and `_forwarded` for the overlay colors.
