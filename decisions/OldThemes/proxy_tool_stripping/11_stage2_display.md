# Stage 2 Implementation — Display Polish

Session 2026-06-05. Implements the four Stage 2 items deferred from Stage 1 (`10_stage1_implementation.md`).
Scope: `render_sections.py` only. No changes to `render_messages.py`, `logging.py`, or `parser.py`.

## What We Did

### Investigation (Phase A)

Read `render_sections.py` (post-Stage-1), `parser.py` (for sys_block field structure), `logging.py`
(for `_stripped`/`_injected` span structure of whole-stripped tools), and a real `_stripped.jsonl`
log to verify whole-stripped tool content.

Resolved four scope questions before coding:

**F3 (tool name-line color):** `use_dual` path labels `s_desc`-only cases with `DIM_YELLOW_BG` on
the NAME line — same color as whole-stripped tools. Fix: `hdr_bg = DIM_GREEN_BG if whole_injected else ''`.
Desc-only change visible only in expanded description content, not the name line.

**F4 (sys unchanged detection):** `parser.py:71` stores `'preview': b.get('text', '')` — the FULL
block text, not truncated. Comparing `preview` text per block is a full content comparison.
Confirmed against real log: block[0] billing header has `chars=81` in two consecutive requests but
`cch=` field differs (`cch=cd00b` → `cch=ee6fc`). Char-count comparison: "unchanged" (wrong).
Preview comparison: "changed" (correct).

**F5 (block-level delta visibility):** F4 and F5 compose naturally — F4 provides the per-block
comparison method, F5 uses it to gate rendering. Implementation: remove the global `sys_unchanged`
variable and the `if sys_unchanged: ... else:` branching entirely. Replace with `prev_block_by_idx`
dict + per-block skip predicate inside the loop. For tools: remove the `(unchanged)` line and
collapse the `if not tools_changed: ... else:` branching — `removed = []` when unchanged, so the
loop is a no-op.

**Marker cleanup (a):** Six locations to clean:
1. Sys block hdr: `label, hdr_bg = '  [STRIPPED]', DIM_YELLOW_BG` → drop `label`, `hdr_bg` alone
2. Tools use_dual hdr: same pattern
3. Tools old-format: `stripped_marker` var
4. Whole-stripped use_dual: `  [STRIPPED]` inline string
5. Whole-stripped old-format: `  [STRIPPED]` inline string
6. Deferred tools: `  [DEFERRED]` inline string

**Marker cleanup (b) — SKIPPED:** Task brief claimed whole-stripped tool content lives in the
`_stripped` log. Verified false: `logging.py:329` stores `s_tools[name] = {"whole": True}` —
marker only, no description. Confirmed against real `_stripped.jsonl` log entry:
`{"Agent": {"whole": true}, ...}`. No content to expand to. `keys.append(None)` left unchanged;
only text labels removed. No `logging.py` change needed.

## What We Found

- The global `sys_unchanged` removal is clean: the entire `if sys_unchanged: lines.append... keys.append... else: use_dual... for sb` structure collapses to `use_dual... prev_block_by_idx... for sb: if skip: continue`. 4-space dedent on the block body, no other structural change.

- `prev_block_by_idx = {b['idx']: b for b in prev_sys_blocks}` is the correct matching strategy since block indices are stable across requests.

- For the tools `(unchanged)` removal: the `else:` block in `if not is_first_request and not tools_changed: ... else: for r_name in removed:` only contained the `removed` loop. When tools are unchanged, `removed = []` → the loop is a no-op whether or not the `else:` wrapper is present. Safe to collapse.

- `isinstance(i_spans[0], (list, tuple))` guard on inline render path: `i_spans` may be `None` when `use_dual` but no inject data for this block. Guard already present in Stage-1 code — untouched.

- Literal Unicode chars (`▼`, `▶`) used in new file vs `'▼'`/`'▶'` escape sequences in the old file. Functionally identical at runtime. Kept as literals in the rewrite.

## Sample Render Verification

Ran against real log `api_requests_opus_monitor_cc_1780517466.jsonl` + dual logs.

**F4 — billing header detection:**
| | Entry 0 | Entry 1 | Old (chars) | New (preview) |
|---|---|---|---|---|
| block[0] chars | 81 | 81 | same → UNCHANGED (wrong) | — |
| block[0] preview | `cch=cd00b` | `cch=ee6fc` | — | differs → CHANGED (correct) |
| block[1] preview | `You are Claude Code...` | `You are Claude Code...` | same | same → skip (correct) |

**F5A — sys block visibility:**
Entry 1 expanded render: shows block[0] (changed preview) + block[2] (new block, absent in entry 0); block[1] absent from render (unchanged, correctly hidden).

**F5B — tools (unchanged) line:**
Second-request same-hash render: shows header + whole-stripped tools (Agent/AskUserQuestion/ScheduleWakeup/ToolSearch as yellow `▶ name`). No `(unchanged)` line. ✓

**F3 + Marker cleanup — tool name-line colors (mock with desc-stripped + whole-injected + whole-stripped + deferred):**
| Tool | Type | Name-line color | Label text |
|---|---|---|---|
| Bash | desc-stripped forwarded | gray | none ✓ |
| mcp__tool1 | whole-injected | GREEN | none ✓ |
| Agent | whole-stripped (blocklisted) | YELLOW | none ✓ |
| CronCreate, WebFetch | deferred | YELLOW | none ✓ |

All assertions passed via automated check.

## LOC Change

`render_sections.py`: 326 → 299 LOC (removed `sys_unchanged` block, `label` vars, `(unchanged)` lines, `else:` branching).

## dev/ Scripts Used

None committed. Verification ran inline from the parent session against real log files.

## Live-Verify Pending

Visual render in the Monitor TUI requires proxy restart. The following behaviors are verified only via sample render and cannot be claimed as live-confirmed:
- Yellow/gray color contrast on tool name lines in a real proxy session
- Billing header block correctly appearing in every request's sys expansion
- Unchanged sys blocks (CC rules prompt, `You are Claude Code` intro) not appearing after req 1

## Decision / Next

Stage 2 complete. No Stage 3 items remain from the OldThemes trail. Pending live-verify (proxy restart) — visual confirmation of all four behaviors in the running Monitor TUI.
