# Wake-Up Hook — Iteration History

## Context

When Opus's background-Bash timer terminates, CC delivers a notification to the running session. Without intervention Opus sees the raw notification text and has no prompt to act on it. Goal: transform the notification into a minimal wake-up hint so Opus runs `worker-cli status` on the next turn.

CC natively delivers two notification shapes:
- **Plain-text BG-exit notification** — emitted when a background Bash task terminates (kill signal or clean exit). Already caught by `strip_bg_completed.py`.
- **`<task-notification>` XML block** — emitted for failed background tasks (`<status>failed</status>`, exit 143/137). Handled in `rules.py` `_apply_first_pass`.

Both shapes were already in the strip pipeline before this work. The iteration history below is about what to do INSTEAD of stripping them.

---

## Iteration 1 — Signal-File IPC (rejected; reverted 01b0665)

### What was built

- `src/menubar/hook_writer.py` extended to emit `/tmp/worker-idle-<name>.signal` on every worker-side Stop event.
- New helper `_inject_worker_wakeup(payload, model_family)` in `src/proxy/rules.py` consumed the signal files on each Opus REQ and appended a `<system-reminder>` block to the last user message.
- Merge commit: `7a597f8`.

### Why rejected

Signal-file IPC is over-engineered relative to what CC already provides natively:

1. CC's native `<task-notification>` fires on timer completion (exit 143/137). The signal file does NOT fire on natural timer completion — it fires on Stop events inside the worker's hook lifecycle, which is a different trigger with different timing.
2. The worker name embedded in the signal file is not needed: Opus can run `worker-cli status` to discover idle workers without being told a specific name.
3. The "timer killed but signal not yet written" race is inherent in the IPC design — the native notification has no such race.
4. The proxy was ALREADY catching both notification shapes and stripping them. The correct architecture is REPLACE-instead-of-strip, not a parallel IPC channel.

### Action

Revert commit `7a597f8` → revert commit `01b0665`. Signal-file approach dropped entirely.

---

## Iteration 2 — Replace-in-Strip with `<system-reminder>` Wrap (partial; 132c7c5)

### What was built

- `strip_bg_completed.py` modified: first kill-notification replaced with a multi-line `<system-reminder>` block (`_WAKEUP_SR`), further notifications stripped.
- `rules.py` `_apply_first_pass` modified: when `<task-notification>` content contains `<status>failed</status>`, appends the same `_WAKEUP_SR` block to the trimmed content. Mod name: `replaced_task_notification`.
- `strip_bg_completed.py` path: mod name `replaced_bg_completed_text`.
- Smokes passed. Merged.

### Problem identified

`_WAKEUP_SR` contained a literal `<system-reminder>…</system-reminder>` wrapper. This caused `strip_vocab.py` (the monitor classifier) to see a `<system-reminder>` block in outgoing content with no strip-rule attributed to it → emitted `SUS:<SR>` (suspicious SR detected but not attributed to any known modifier). This is a false positive — the proxy itself ADDED the SR, it didn't leak one from CC.

Fix would require a follow-up to `strip_vocab.py`: register the two new mod names AND exclude proxy-injected SRs from SUS detection.

---

## Iteration 3 — Plain Text (current; 903c605)

### What was built

- `_WAKEUP_SR` constant renamed to `_WAKEUP_TEXT = 'worker idle\n'` in `strip_bg_completed.py`.
- Helper renamed: `_append_wakeup_sr_to_content` → `_append_wakeup_text_to_content` in `rules.py`.
- All call sites updated. `strip_bg_completed.py` replace path returns `_WAKEUP_TEXT` directly.
- DOCS.md updated to reflect plain-text replacement.

### Benefit

Plain text has no `<system-reminder>` tags → bypasses the SR-strip pipeline entirely. `strip_vocab.py` sees no SR block to classify → no `SUS:<SR>` false positive. The `strip_vocab.py` follow-up from Iteration 2 is no longer needed.

Opus sees `worker idle` on the wake-up turn — sufficient to trigger `worker-cli status`.

### Mod names (unchanged from Iteration 2)

- `replaced_bg_completed_text` — BG-exit plain-text path (`strip_bg_completed.py`)
- `replaced_task_notification` — `<task-notification>` failed path (`rules.py` `_apply_first_pass`)
- `trimmed_task_notification` — `<task-notification>` non-failed path (unchanged behavior)

### Status

Live verification deferred to next session (proxy frozen at session start, does not see code from 903c605 until proxy restart).

---

## Iteration 4 — Menubar Watchdog Removal (2026-05-22)

### What was built (and removed)

Parallel to Iteration 3 (same session): `_notify_opus_workers_idle` added to `src/menubar/bg_timer.py`. Called from `_auto_abort_check` in `app.py` immediately after `_abort_bg_sleep_timers`. Mechanism: on all-workers-idle + active bg timer (5s debounce), after killing the sleep child via SIGTERM, inject `worker <names> idle\nEnter` directly into Opus's tmux pane via `tmux send-keys`. TTY looked up from `_cc_proc_cache` → pane_ref from `tmux list-panes -a`.

### Why removed

User decision: **proxy only**. The watchdog approach was architecturally invasive — it types unsolicited text into the Opus pane as a side-effect of the timer-kill path. The proxy replace-in-strip approach (Iteration 3) achieves the same outcome non-invasively: CC's own `strip_bg_completed.py` replaces the kill-notification with `worker idle\n` before Opus sees it, giving Opus the wake-up context in the normal message stream without any out-of-band pane injection.

### Final architecture

Production wake-up path: `strip_bg_completed.py` (`replaced_bg_completed_text`) + `rules.py` `_apply_first_pass` (`replaced_task_notification`). Auto-abort (`_abort_bg_sleep_timers`) remains in the menubar tick loop — it is the trigger that causes the timer to terminate early, which in turn causes CC to deliver the notification that the proxy replaces. The two halves are complementary: menubar kills the timer, proxy delivers the signal.

---

## Iteration 5 — Generalized wake-up text (2026-05-22)

`_WAKEUP_TEXT` changed from `'worker idle\n'` to `'background done — check worker or other process\n'`. Rationale: the proxy replace-path fires for ALL `<task-notification>` (failed) and ALL `Background command "…" failed/completed (exit code 143/137)` — both worker timers AND non-worker background tasks (rag-cli, builds, etc.). The old text was misleading for the non-worker case. Generic wording keeps the hint accurate regardless of background-task source.

---

## Iteration 6 — Dedup + Universal Non-Failed Wake-Up (2026-05-22, later same day, commit `fcfe6c1`)

### Problems identified live

Two bugs discovered via proxy log inspection during a session debugging "Punkt im Proxy-Pane statt Wake-Up-Text":

1. **Double-Inject:** when CC delivers BOTH notification shapes for the same background-task termination (routine case — CC fires `<task-notification status=failed>` AND the plain-text `Background command "..." exit code 143` in the same user-turn), both replace-paths fire independently on the SAME message. Each appends a wake-up text block. Result: the message has TWO identical `_WAKEUP_TEXT` blocks back-to-back. Proxy-pane screenshot showed msg[74] with both `EFF:TN` and `EFF:BGK` strip-labels followed by two text-blocks `[0] 47c background done — check worker or other process` and `[1] 48c background done — check worker or other process`.

2. **Non-failed TN gets no wake-up:** `_apply_first_pass` gated `_append_wakeup_text_to_content` behind `is_failed_bg = "<status>failed</status>" in old_content`. Non-failed TNs (normal task completion, e.g. `<status>done</status>`) got their XML stripped down to a `"."` placeholder (from `payload_helpers.py::_strip_task_notification_tags` line 167 — empty content becomes `"."` to avoid empty-block API errors) without any wake-up indication.

### Fix (commit `fcfe6c1`)

**Bug 1 — Dedup:** new helper `_dedup_wakeup_blocks(messages) → messages` runs as final message-side pass in `apply_modification_rules` (after `_apply_bg_exit_strip`, before `_apply_system_passes`). Per user-message: collapses multiple `_WAKEUP_TEXT` text-blocks to one (keep first, drop subsequent duplicates). Comparison uses `rstrip('\n')` to treat TN-path (with trailing `\n`) and BGK-path (without `\n`) as duplicates. Operates ONLY on `msg["content"]` — never touches `stripped_msg_removed` (display invariant: wake-up text is INJECTED into outgoing payload, NOT stripped from it; proxy-pane shows wake-up blocks as normal text, never as dim-yellow strip chunks).

**Bug 2 — Universal Wake-Up:** removed the `if is_failed_bg:` guard around `_append_wakeup_text_to_content` in `_apply_first_pass`. Wake-up now appended to ALL `<task-notification>` blocks regardless of status. Mod-name semantics preserved: `replaced_task_notification` still indicates failed TN, `trimmed_task_notification` now means "non-failed TN stripped + wake-up appended".

### Smoke (7/7 PASS in `/tmp/wakeup_dedup_smoke.py`)

| # | Scenario | Result |
|---|---|---|
| 1 | Failed TN + BGK in SAME text block | 1 wakeup block |
| 2 | Non-failed TN only | 1 wakeup block (new behavior) |
| 3 | Non-failed TN + BGK | 1 wakeup block |
| 4 | Failed TN only (regression) | 1 wakeup block |
| 5 | BGK only (regression) | 1 wakeup block |
| 6 | Failed TN + BGK in SEPARATE blocks (live `[0] 47c` + `[1] 48c` screenshot scenario) | 1 wakeup block |
| 7 | Display invariant: `_WAKEUP_TEXT` absent from `stripped_msg_removed` across T1/T2/T3/T6 | all pass |

### Architecture status post-Iteration-6

1. **Detection:** any of {`<task-notification>` block, plain-text BGK exit notification} present in user-turn.
2. **Injection:** `_append_wakeup_text_to_content` (any TN, via `_apply_first_pass`) OR `_strip_bg_from_text` inline replacement (BGK, via `_apply_bg_exit_strip`). Both fire independently.
3. **Dedup:** `_dedup_wakeup_blocks` final pass guarantees ≤ 1 wake-up block per user-message regardless of how many injectors fired.
4. **Display invariant:** wake-up text never enters `stripped_msg_removed`; proxy-pane renders it as normal content.

### Quellen

- decisions/pipe05_proxy_cache.md (IST reflects `fcfe6c1`).
- src/proxy/rules.py `_dedup_wakeup_blocks`, `_apply_first_pass`.
- src/proxy/payload_helpers.py `_strip_task_notification_tags` line 167 (the `"."` placeholder source).
- src/proxy/strip_bg_completed.py (BGK path, unchanged).
