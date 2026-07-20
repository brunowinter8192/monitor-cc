# ccwrap Phase 2 — Decorative Byte Filter Strategy

## Status (2026-05-29): Deferred — not autonomously executable

Phase 2 depends on Phase-1 `.ansi.log` collection from a REAL interactive CC session in Ghostty (user runs `python3 -m src.ccwrap`, makes several tool calls) → then byte analysis + the two local-verify gates below. That needs interactive user involvement, not an autonomous worker. The tracking task was closed 2026-05-29: the complete strategy lives here, nothing is lost. Resume when the user wants to collect Phase-1 data; entry point is the three-way decision tree below.

## Related context

- The original investigation (Hypothesis 3: ANSI sequences bypass Ghostty config) is the open thread Phase 2 closes
- What Phase 1 built: smoke test results; known limitations
- `src/ccwrap/DOCS.md` — current package structure, modules, gotchas

---

## Goal

Phase 2 uses the `.ansi.log` data collected during a real CC session (Phase 1) to identify the specific ANSI sequence that triggers Ghostty's scroll-to-bottom, then adds a byte-rewriting filter to `src/ccwrap/` that suppresses only that sequence. The visible TUI output must be bit-identical before and after the filter; only rendering hints to the terminal are removed. Deployment requires two explicit pass criteria before landing in production.

---

## Content vs decorative bytes

CC's TUI output on every tool_use render mixes two byte categories:

**Content bytes** — carry visible information. Stripping any of these degrades the display.

| Example | Meaning |
|---|---|
| `⏺ Bash(echo hello)` (UTF-8 text) | The tool call label the user reads |
| `\033[34m` / `\033[0m` (CSI SGR) | Foreground color on/off |
| `\033[2J` + `\033[H` (erase + home) | Full-screen repaint (Monitor_CC's render cycle) |
| `\033[A` / `\033[B` (cursor up/down) | Cursor positioning within the layout |

**Decorative bytes** — rendering hints: atomicity guarantees, scroll-region fencing, cursor
state checkpoints. The terminal uses these for paint-ordering only. Strip them → visible
content unchanged, pacing/atomicity changed (at most: a brief partial-render flash).

| Example | Meaning |
|---|---|
| `\033[?2026h` … `\033[?2026l` | Synchronized Output Mode ON/OFF — tells terminal to buffer until OFF before painting |
| `\033[r` | Scroll region reset (no-arg = full screen) |
| `\033[s` / `\033[u` | Cursor save/restore (ANSI variant) |
| `\033 7` / `\033 8` | Cursor save/restore (DEC variant) |

**Hypothetical tool_use byte sequence** (annotated):

```
\033[?2026h          ← decorative: sync-output ON  ← PRIME SUSPECT
\033[?25l            ← decorative: hide cursor
\033[H               ← content: cursor home (part of full repaint)
\033[2J              ← content: erase display (full repaint)
... rendered TUI lines with SGR colors ...
⏺ Bash(echo hello)\033[0m\r\n   ← content: tool call text
\033[?25h            ← decorative: show cursor
\033[?2026l          ← decorative: sync-output OFF ← PRIME SUSPECT
```

If Ghostty interprets `\033[?2026l` (sync-output OFF = "commit the buffered frame") as a
scroll-to-bottom trigger, stripping the `\033[?2026h`…`\033[?2026l` pair eliminates the
trigger without altering any visible character or color.

---

## Hypothesis

**Synchronized Output Mode (`CSI ?2026h` / `CSI ?2026l`) is the prime suspect.**

Reasoning:
1. CC's TUI does a full-screen repaint on every render cycle (`\033[2J\033[H` confirmed in `initial.md` line 71 and smoke test output). Synchronized Output Mode is the standard way to suppress the flicker that would otherwise result from the partial-erase-then-repaint sequence.
2. `\033[?2026l` (sync OFF) is semantically "I have finished painting a frame — display it now." A terminal that conflates "new frame committed" with "scroll to show latest output" would jump here.
3. Thinking phases and text streaming do NOT trigger jumps (per original symptom description). Thinking output is streamed without full-screen repaints; it is unlikely to emit sync-output wrappers. Tool_use renders do full repaints → sync wrappers → jump.
4. The jump correlates with tool_use rendering, not with raw output volume, which is consistent with a per-frame signal rather than a byte-count threshold.

Secondary suspects (in order of likelihood):
- `CSI r` (scroll region reset) — some terminals scroll to the bottom when the scroll region is reset to full-screen.
- `CSI ?47h` / `CSI ?1049h` (alternate screen enter/exit) — if CC ever enters alternate screen mode, exit returns the viewport to normal screen position. Less likely (CC runs in-line, not in alternate screen).

---

## Three-outcome decision tree

After collecting `.ansi.log` data from a real CC session:

**Outcome 1 — Clean separable trigger identified**

A single sequence (or tight symmetric pair) appears consistently at tool_use render events
and is absent during thinking/streaming. It is decorative (removing it leaves visible
content unchanged).

→ Build filter in `src/ccwrap/filter.py` (new module): intercept the trigger sequence(s)
on the `master_fd → stdout` path in `_io_loop`, drop them from the byte stream. Content
bytes pass through unmodified. Run local verification (see Safety Net). Deploy if both
pass criteria met.

**Outcome 2 — Trigger entangled with essential rendering**

The sequence that correlates with jumps is also load-bearing for layout (e.g. `\033[H`
cursor home IS part of the repaint — stripping it would corrupt the display). No clean
strip point exists.

→ Document the sackgasse in this file (add findings section). Do NOT deploy Phase 2.
Accept the `scroll-to-bottom = no-keystroke, no-output` Ghostty config as the permanent
fix. Wrapper stays in passthrough mode; Phase 1 logs remain available for future
investigation if Ghostty's behavior changes.

**Outcome 3 — Multiple context-dependent triggers**

Several unrelated sequences each contribute to jumps depending on context (session state,
CC version, OS). A correct filter requires pattern matching on context, not just sequence
identity.

→ Cost/benefit: if the set of triggers is small (≤3, clearly bounded), extend Outcome 1
approach with a multi-pattern filter. If the set is large or context-dependent in ways
that require stateful tracking, abandon Phase 2 deployment — the maintenance cost exceeds
the UX benefit of the workaround already in place.

---

## Safety net

Phase 2 filter is NEVER deployed before both pass criteria are confirmed:

**Gate 1 — Phase 1 data confirms a clean trigger.**
Read the `.ansi.log` from a real CC session. Verify the suspect sequence appears at
tool_use render timestamps and is absent during thinking/streaming. Verify removing it
leaves visible byte content unchanged (cross-check with `.bin`).

**Gate 2 — Local verification in real Ghostty.**
User runs `python3 -m src.ccwrap [--project <path>]` with filter mode active in a real
Ghostty window. Executes 3–5 tool calls that previously triggered jumps. Pass criteria:
(a) viewport does NOT jump during or after any tool call; (b) TUI renders identically to
unfiltered CC (no garbled lines, no missing color, no missing tool call text).

If either gate fails → do not merge filter to `src/`. The wrapper stays in passthrough
mode. Document the failure in a `ccwrap_phase2_results.md` in this folder.

---

## Alternatives rejected

**Suppress all ANSI in tool_use windows**
Requires detecting "tool_use windows" in the byte stream without a terminal emulator
(the raw bytes don't label their semantic context). Even if detectable, stripping all
ANSI during tool_use renders removes color, cursor positioning, and layout — CC's TUI
becomes unreadable. Rejected: destructive.

**Alternate screen injection (enter before CC, exit after)**
Makes CC behave like vim/htop: the TUI occupies the full terminal, scrollback is
inaccessible during the session. The scroll-lock UX improvement is moot if there is no
scrollback to protect. Rejected: changes UX fundamentally.

**Counter-scroll injection (emit scroll-up after each jump)**
Terminals don't expose a scroll-position query (`\033[?18t` etc. are not universally
supported and Ghostty's support is untested). Without knowing current scroll position,
injecting N scroll-up lines after a jump would over- or under-correct. Rejected:
unreliable.

**Ghostty issue tracker / upstream fix**
CC #826 is open since April 2025, cross-terminal, unfixed. Waiting for upstream is an
option but has indefinite timeline. The wrapper approach is deployable now and removable
later (just stop launching via `python3 -m src.ccwrap`) with zero permanent coupling.
Not rejected — complementary. If upstream fixes the root cause, the wrapper becomes a no-op.

---

## Strategic value of the wrapper architecture

The PTY wrapper is a general byte-level interposition layer between the user's terminal
and CC. Phase 2's jump fix is the first concrete use case, but the infrastructure is
reusable for any future intervention:

- **Permission-prompt highlighting**: detect `\033]` OSC sequences or specific text
  patterns (e.g. `Allow this action?`) and inject ANSI color around them.
- **Tool-output redaction**: strip or hash sensitive strings (API keys, tokens) from
  the live byte stream before they appear in the terminal scrollback.
- **Latency annotation**: inject timing overlays next to tool_use labels.
- **Capture for external consumers**: the `.bin` log is a complete, timestamped record
  of every byte CC emits — usable for replay, diffing across CC versions, or feeding
  into a separate TUI analyzer.

All of these require zero changes to CC itself, zero changes to Ghostty config, and are
fully reversible by not launching via the wrapper.
