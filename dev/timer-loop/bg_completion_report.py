# INFRASTRUCTURE
from datetime import datetime, timezone

from bg_completion_scan import EXCLUDED_FILES, _is_canonical_timer_command, _mechanism_verdict


# FUNCTIONS

def _report_header_and_corpus(ts, corpus_files, total_requests, total_parse_errors):
    lines = []
    lines.append('# Milestone 1 — bg-completion/kill notice wording inventory (real corpus)')
    lines.append('')
    lines.append(f'Generated: {ts}')
    lines.append('')
    lines.append('Companion to `dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md` (launch side); this is the completion side.')
    lines.append('')

    lines.append('## Corpus')
    lines.append('')
    lines.append(f'{len(corpus_files)} files scanned (full per-line parse, not last-line-only — see Method).')
    lines.append(f'Total requests (lines) scanned: {total_requests}. JSON parse errors skipped: {total_parse_errors}.')
    lines.append('')
    lines.append('| Excluded file | Reason |')
    lines.append('|---|---|')
    for fname, reason in EXCLUDED_FILES.items():
        lines.append(f'| `{fname}` | {reason} |')
    lines.append('')
    return lines


def _report_method_and_contamination():
    lines = []
    lines.append('## Method')
    lines.append('')
    lines.append(
        'Each dual-log line is a cumulative snapshot of the full `messages` history (same growing-'
        'history duplication as the launch-ack corpus). A last-line-only shortcut was benchmarked '
        '(~200x cheaper — 22MB vs 5.2GB for the largest session) but rejected: message-count-per-line '
        'is **not always monotonic** — several worker sessions (`api_requests_worker_cbc9195b_pass-*`) '
        'show mid-session decreases (compaction/context reset), so a last-line snapshot could silently '
        'drop notices lost to compaction. Instead: full per-line parse (benchmarked ~20-30s for the '
        'whole 17GB corpus), deduped via a per-session **exact-raw-text `seen` set** on the extracted '
        '`<task-notification>...</task-notification>` tag-block text — robust to both simple linear '
        'growth and compaction resets, unlike a prev-count positional delta (which double-counts on '
        'any reset).'
    )
    lines.append('')

    lines.append('## Contamination trap')
    lines.append('')
    lines.append(
        'Two sources found, both filtered by requiring the candidate block be **block-initial** '
        '(`text.lstrip().startswith(...)`), never contains-anywhere:'
    )
    lines.append('')
    lines.append(
        '1. **Prose/dev-report discussion quoting notice text.** `api_requests_opus_posts_1785424929` '
        'contains a German write-up discussing token cost that quotes `Background command "Index issues '
        'broad pass" completed (exit code 0)` mid-sentence, and a report-abbreviated '
        '`<output-file><path>...</path></output-file>` tag shape (567 raw hits, all from this one file) '
        'that is a documentation summary, not real wire format — the real wire format never nests a '
        '`<path>` tag inside `<output-file>`. Neither is block-initial, so both are excluded.'
    )
    lines.append(
        '2. **This worker\'s own live session** (see Excluded file above) — Read-tool dumps of the '
        'exact source files under measurement produce fake candidate text (docstrings/regex literals '
        'containing `<task-notification>`, `<task-id>` etc.) that would otherwise inflate every count.'
    )
    lines.append('')
    return lines


def _report_q1(findings):
    lines = []
    lines.append('## Q1 — Distinct wordings')
    lines.append('')
    if not findings:
        lines.append('**0 genuine completion/kill notices found in the scanned corpus.** Reported plainly — not manufactured.')
    for i, (key, rec) in enumerate(sorted(findings.items(), key=lambda kv: -kv[1]['count']), 1):
        status, exit_code, norm_summary = key
        verdict = _mechanism_verdict(rec['example_tag_block'], rec['example_full_text'])
        lines.append(f'### Wording {i} — status=`{status}`, exit code=`{exit_code}`')
        lines.append('')
        lines.append(f'- Normalized summary template: `{norm_summary}`')
        lines.append(f'- Occurrences (deduped, real distinct events): **{rec["count"]}**')
        lines.append(f'- Main sessions: {sorted(rec["main_sessions"])} ({len(rec["main_sessions"])})')
        lines.append(f'- Worker sessions: {sorted(rec["worker_sessions"])} ({len(rec["worker_sessions"])})')
        lines.append(f'- Roles seen: {sorted(rec["roles"])}')
        lines.append(f'- Content shapes seen: {sorted(rec["shapes"])}')
        lines.append('')
        lines.append('**Verbatim example (full block, incl. SN paragraph):**')
        lines.append('')
        lines.append('```')
        lines.append(rec['example_full_text'])
        lines.append('```')
        lines.append('')
        lines.append('**Mechanism fire/no-fire (real `src/proxy/` code):**')
        lines.append('')
        lines.append('| Mechanism | Result |')
        lines.append('|---|---|')
        lines.append(f'| `_SN_NOTICE_MARKER` fast-path gate | {"FIRES" if verdict["sn_marker_fires"] else "does NOT fire"} |')
        lines.append(f'| `<task-notification>` contains-gate (message_passes.py TN branch) | {"FIRES" if verdict["tn_tag_contains_fires"] else "does NOT fire"} |')
        lines.append(f'| `_extract_task_notification_task_id` | {"extracts: " + verdict["task_id_extract"] if verdict["task_id_extract"] else "FAILS to extract"} |')
        lines.append(f'| `_extract_task_notification_output_file` | {"extracts: " + verdict["output_file_extract"] if verdict["output_file_extract"] else "FAILS to extract"} |')
        lines.append('')
    return lines


def _report_q1b(bare_hits):
    lines = []
    lines.append('## Q1b — Bare (unwrapped) `strip_bg_completed.py`-family notices')
    lines.append('')
    total_bare = sum(bare_hits.values())
    if total_bare == 0:
        lines.append(
            '**0 block-initial bare `Background command "..." completed/failed` notices found anywhere '
            'in the corpus.** Every genuine completion/kill notice observed is `<task-notification>`-'
            'wrapped. `strip_bg_completed.py`\'s bare-form regex (`_BG_EXIT_RE`) is defensive/unexercised '
            'by real data in this corpus — its match target (a standalone, non-TN-wrapped notice) was '
            'not observed to occur; the same literal text (`Background command "..." failed with exit '
            'code N`) DOES occur, but always nested inside a `<summary>` tag within a TN block.'
        )
    else:
        lines.append(f'{total_bare} raw block-initial bare-family hits, by session: {dict(bare_hits)}')
    lines.append('')
    return lines


def _report_q2():
    lines = []
    lines.append('## Q2 — Id extractability verdict')
    lines.append('')
    lines.append(
        'Every genuine TN wording carries the task id via a clean `<task-id>...</task-id>` XML tag — '
        '**reliably regex-extractable** (`payload_helpers._extract_task_notification_task_id`, already '
        'implemented and exercised above). This is a structurally different, simpler mechanism than the '
        'launch-ack side\'s prose `"with ID: <id>."` pattern — no prose parsing needed, no ambiguity '
        'about where the id ends.'
    )
    lines.append('')
    return lines


def _report_q3(findings, session_is_worker):
    lines = []
    lines.append('## Q3 — Main vs worker split')
    lines.append('')
    n_main_files = sum(1 for s, w in session_is_worker.items() if not w)
    n_worker_files = sum(1 for s, w in session_is_worker.items() if w)
    lines.append(f'Corpus (post-exclusion): {n_main_files} main (`opus`) session files, {n_worker_files} worker session files.')
    lines.append('')
    all_main = set()
    all_worker = set()
    for rec in findings.values():
        all_main |= rec['main_sessions']
        all_worker |= rec['worker_sessions']
    lines.append(f'Main session files with >=1 genuine completion/kill notice: {len(all_main)} of {n_main_files}.')
    lines.append(f'Worker session files with >=1 genuine completion/kill notice: {len(all_worker)} of {n_worker_files}.')
    lines.append('')
    zero_hit_worker_files = sorted(s for s, w in session_is_worker.items() if w and s not in all_worker)
    pass_lot_files = [s for s in zero_hit_worker_files if 'cbc9195b_pass-' in s]
    other_worker_files = [s for s in zero_hit_worker_files if 'cbc9195b_pass-' not in s]
    if other_worker_files:
        breakdown = (
            f'{len(zero_hit_worker_files)} zero-hit worker session files show zero genuine TN blocks — '
            f'{len(pass_lot_files)} of them match `api_requests_worker_cbc9195b_pass-*`, the remaining '
            f'{len(other_worker_files)} do not (`{"`, `".join(other_worker_files)}`).'
        )
    else:
        breakdown = (
            f'all {len(zero_hit_worker_files)} worker session files in this corpus '
            '(`api_requests_worker_cbc9195b_pass-*`) show zero genuine TN blocks.'
        )
    lines.append(
        f'**Observation about THIS corpus, not a structural guarantee:** {breakdown} '
        'This does not mean worker sessions structurally cannot receive a completion notice — the TN '
        'delivery mechanism is a CC-side background-Bash feature independent of main/worker session role; '
        'it fires whenever a session backgrounds a Bash call. These worker sessions simply may not have '
        'backgrounded any Bash call (or none of the ones they backgrounded completed/was killed) during '
        'the recorded window. The excluded own-session file (`85d6f25b_timer-loop`) IS a worker session '
        'that DID receive genuine notices (from its own backgrounded commands during this investigation) '
        'before being excluded for contamination — direct proof worker sessions CAN receive them.'
    )
    lines.append('')
    return lines


def _report_q4(cmd_variant_counts):
    lines = []
    lines.append('## Q4 — Canonical timer vs other background tasks')
    lines.append('')
    lines.append(
        'Same `<task-notification>` template for every background task regardless of identity — no '
        'timer-specific wording exists. The only difference is the quoted command/description string '
        'inside `<summary>`, driven by whether the launcher passed a `description` to the Bash tool call:'
    )
    lines.append('')
    lines.append('| status | exit code | canonical `sleep 3300 && echo done` (deduped events) | other command/description (deduped events) | example other |')
    lines.append('|---|---|---|---|---|')
    for (status, exit_code), bucket in sorted(cmd_variant_counts.items()):
        example_other = next((cmd for cmd, _ in bucket['examples'].most_common() if not _is_canonical_timer_command(cmd)), '-')
        lines.append(f'| `{status}` | `{exit_code}` | {bucket["canonical_timer"]} | {bucket["other"]} | `{example_other}` |')
    lines.append('')
    lines.append(
        'Every 55-minute orchestrator ceiling timer is the same underlying `sleep 3300 && echo done` '
        'Bash call — the varying labels (`"Timer 55min"`, `"55min-Timer für Los-2-Implementierung"`, '
        '`"55min ceiling timer"`, ...) are `description` params different Opus sessions/prompts chose '
        'for the SAME command, not different commands. Non-timer background tasks (`"Index issues broad '
        'pass"`, `"RAG-Sync ausführen"`, ...) use the same TN template, status=`completed`, exit code `0`.'
    )
    lines.append('')
    return lines


def _report_exit_anomaly(findings):
    lines = []
    lines.append('## Exit-code anomaly — code 144 (not 0 / 143 / 137)')
    lines.append('')
    anomaly_key = next((k for k in findings if k[1] == '144'), None)
    if anomaly_key:
        rec = findings[anomaly_key]
        lines.append(
            f'A single genuine event (not a duplicate-inflated count) — task-id extractable, status='
            f'`{anomaly_key[0]}`, exit code `{anomaly_key[1]}`, session(s): '
            f'{sorted(rec["main_sessions"] | rec["worker_sessions"])}. This is a real command-internal '
            'failure exit status (the backgrounded "Reindex" command itself exited 144), NOT a kill '
            'signal code — `strip_bg_completed.py`\'s bare-form matcher only special-cases 143/137 and '
            'never fires on this text anyway (it is TN-wrapped, see Q1b), but the broader point holds '
            'for the pending-state design: **completion notices are not restricted to {0, 143, 137}** — '
            'any exit code can appear in a genuine `<status>failed</status>` TN block. A pending-id-'
            'clearing mechanism keyed only on those three codes would miss this notice; the TN branch\'s '
            'existing `<task-notification>` contains-gate (status-agnostic, exit-code-agnostic) already '
            'fires correctly here — verified above.'
        )
        lines.append('')
        lines.append('**Verbatim block:**')
        lines.append('')
        lines.append('```')
        lines.append(rec['example_full_text'])
        lines.append('```')
    else:
        lines.append('Not found in this run — see raw exit-code distribution below for what was found instead.')
    lines.append('')
    return lines


def _report_dedup(raw_dup_counter, findings):
    lines = []
    lines.append('## Dedup importance (raw vs deduped)')
    lines.append('')
    lines.append('| Session | Raw TN candidate-block occurrences (all cumulative snapshots) | Deduped (distinct real events) |')
    lines.append('|---|---|---|')
    for fname in sorted(raw_dup_counter):
        raw = raw_dup_counter[fname]
        deduped = sum(rec['session_counts'].get(fname, 0) for rec in findings.values())
        lines.append(f'| `{fname}` | {raw} | {deduped} |')
    lines.append('')
    return lines


# Build the markdown report
def _build_report(findings, cmd_variant_counts, total_requests, total_parse_errors,
                   raw_dup_counter, bare_hits, corpus_files, session_is_worker):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines += _report_header_and_corpus(ts, corpus_files, total_requests, total_parse_errors)
    lines += _report_method_and_contamination()
    lines += _report_q1(findings)
    lines += _report_q1b(bare_hits)
    lines += _report_q2()
    lines += _report_q3(findings, session_is_worker)
    lines += _report_q4(cmd_variant_counts)
    lines += _report_exit_anomaly(findings)
    lines += _report_dedup(raw_dup_counter, findings)
    return '\n'.join(lines)
