# RAG Query Audit — 2026-05-20T21:03

## Source JSONLs

- `api_requests_opus_monitor_cc_1778339095.jsonl` (228 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1778351487.jsonl` (134 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1778368827.jsonl` (199 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1778421335.jsonl` (175 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1778424911.jsonl` (180 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1778512886.jsonl` (119 events, 1 rag-cli calls)
- `api_requests_opus_monitor_cc_1778529559.jsonl` (380 events, 1 rag-cli calls)
- `api_requests_opus_monitor_cc_1778596205.jsonl` (220 events, 8 rag-cli calls)
- `api_requests_opus_monitor_cc_1778631643.jsonl` (126 events, 10 rag-cli calls)
- `api_requests_opus_monitor_cc_1778958534.jsonl` (1 events, 0 rag-cli calls)
- `api_requests_opus_monitor_cc_1779120726.jsonl` (187 events, 2 rag-cli calls)
- `api_requests_opus_monitor_cc_1779203353.jsonl` (303 events, 1 rag-cli calls)
- `api_requests_opus_monitor_cc_1779227238.jsonl` (291 events, 9 rag-cli calls)
- `api_requests_opus_monitor_cc_1779236062.jsonl` (215 events, 6 rag-cli calls)
- `api_requests_opus_monitor_cc_1779290903.jsonl` (199 events, 6 rag-cli calls)

Total sessions analyzed: 15. Total events: 2957. Total rag-cli calls (unique): 44. Unique topics (jaccard≥0.2): 36.

## Summary

- Single-query topics: 31 / Multi-query topics: 5
- Calls in multi-query topics (follow-up rounds): 13 / 44 (29%)
- Collections used: Monitor_CC-meta (30), Monitor_CC-features (12), RAG-meta (2)
- Calls with chunk_count=0 (Miss): 8
- Calls with truncated result (CC 5k/5k split): 1
- Calls with no tool_result found in logs: 13

## Topic Overview

Clustering: greedy chain-link per session, jaccard ≥ 0.2 on word tokens (stopwords excluded).

| Topic | Session-Log | Queries | Follow-up? | Collections | classification (manual) |
|-------|------------|---------|-----------|-------------|------------------------|
| T001 | `1778512886` | 1 | — | Monitor_CC-meta | _ |
| T002 | `1778529559` | 1 | — | Monitor_CC-meta | _ |
| T003 | `1778596205` | 1 | — | RAG-meta | _ |
| T004 | `1778596205` | 1 | — | Monitor_CC-meta | _ |
| T005 | `1778596205` | 2 | yes | Monitor_CC-meta | _ |
| T006 | `1778596205` | 1 | — | Monitor_CC-meta | _ |
| T007 | `1778596205` | 1 | — | Monitor_CC-features | _ |
| T008 | `1778596205` | 1 | — | Monitor_CC-meta | _ |
| T009 | `1778596205` | 1 | — | RAG-meta | _ |
| T010 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T011 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T012 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T013 | `1778631643` | 1 | — | Monitor_CC-features | _ |
| T014 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T015 | `1778631643` | 1 | — | Monitor_CC-features | _ |
| T016 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T017 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T018 | `1778631643` | 1 | — | Monitor_CC-meta | _ |
| T019 | `1778631643` | 1 | — | Monitor_CC-features | _ |
| T020 | `1779120726` | 1 | — | Monitor_CC-meta | _ |
| T021 | `1779120726` | 1 | — | Monitor_CC-meta | _ |
| T022 | `1779203353` | 1 | — | Monitor_CC-meta | _ |
| T023 | `1779227238` | 2 | yes | Monitor_CC-meta | _ |
| T024 | `1779227238` | 4 | yes | Monitor_CC-features, Monitor_CC-meta | _ |
| T025 | `1779227238` | 1 | — | Monitor_CC-meta | _ |
| T026 | `1779227238` | 1 | — | Monitor_CC-features | _ |
| T027 | `1779227238` | 1 | — | Monitor_CC-features | _ |
| T028 | `1779236062` | 3 | yes | Monitor_CC-features, Monitor_CC-meta | _ |
| T029 | `1779236062` | 1 | — | Monitor_CC-meta | _ |
| T030 | `1779236062` | 1 | — | Monitor_CC-meta | _ |
| T031 | `1779236062` | 1 | — | Monitor_CC-features | _ |
| T032 | `1779290903` | 1 | — | Monitor_CC-meta | _ |
| T033 | `1779290903` | 2 | yes | Monitor_CC-meta | _ |
| T034 | `1779290903` | 1 | — | Monitor_CC-meta | _ |
| T035 | `1779290903` | 1 | — | Monitor_CC-features | _ |
| T036 | `1779290903` | 1 | — | Monitor_CC-features | _ |

## Per-Topic Detail

Manual columns: **hit_quality** = Brauchbar / Zu-eng / Zu-breit / Miss. **classification** per topic = WIN-RAG / WIN-Direct / Tie.

### T001 — 1778512886

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | documentation rule audit drift | Monitor_CC-meta | def | 273 | 0 | — | _ |

**classification (manual):** _

### T002 — 1778529559

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | refactor cluster live-verify 2026-05-12 | Monitor_CC-meta | def | 583 | 0 | — | _ |

**classification (manual):** _

### T003 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | server preset idle stop auto shutdown countdown | RAG-meta | 5 | 10041 | 7 | yes | _ |

**classification (manual):** _

### T004 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | gpu_pane rendering status field unknown question mark | Monitor_CC-meta | 5 | — | — | — | _ |

**classification (manual):** _

### T005 — 1778596205
*2 queries — follow-up topic*

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | tool error log proxy api_requests jsonl tool_use_error tool_result | Monitor_CC-meta | 6 | 24857 | 14 | — | _ |
| 2 | tool failure analysis extract_failed proxy jsonl | Monitor_CC-meta | def | 782 | 0 | — | _ |

**classification (manual):** _

### T006 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | tool use rule violation detection analysis script dev | Monitor_CC-meta | 4 | — | — | — | _ |

**classification (manual):** _

### T007 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | tool error classification audit analysis | Monitor_CC-features | 4 | — | — | — | _ |

**classification (manual):** _

### T008 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar tool session status detection background tasks | Monitor_CC-meta | 8 | 14813 | 8 | — | _ |

**classification (manual):** _

### T009 — 1778596205

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | server log_path llama-port log file path construction spawn | RAG-meta | 6 | 10330 | 6 | — | _ |

**classification (manual):** _

### T010 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | proxy api_requests jsonl log path session | Monitor_CC-meta | 4 | — | — | — | _ |

**classification (manual):** _

### T011 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar icon app.title NSAttributedString baseline rumps | Monitor_CC-meta | 4 | — | — | — | _ |

**classification (manual):** _

### T012 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | session status idle working JSONL mtime detection threshold | Monitor_CC-meta | 4 | 23553 | 12 | — | _ |

**classification (manual):** _

### T013 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | worker context death threshold sonnet | Monitor_CC-features | def | 134 | 0 | — | _ |

**classification (manual):** _

### T014 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar cmd+l hotkey toggle dropdown | Monitor_CC-meta | 5 | 8887 | 5 | — | _ |

**classification (manual):** _

### T015 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | worker revive cc session resume tmux | Monitor_CC-features | def | 133 | 0 | — | _ |

**classification (manual):** _

### T016 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | proxy thinking budget effort injection model rules | Monitor_CC-meta | 6 | — | — | — | _ |

**classification (manual):** _

### T017 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | proxy rules.py addon modify request payload | Monitor_CC-meta | 4 | 17624 | 10 | — | _ |

**classification (manual):** _

### T018 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar app status bar architecture src/menubar | Monitor_CC-meta | 5 | 17224 | 9 | — | _ |

**classification (manual):** _

### T019 — 1778631643

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar NSMenu NSPanel refactor | Monitor_CC-features | 4 | — | — | — | _ |

**classification (manual):** _

### T020 — 1779120726

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | proxy pane copy button | Monitor_CC-meta | def | 128 | 0 | — | _ |

**classification (manual):** _

### T021 — 1779120726

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar launch hotkey Cmd+L Carbon startup | Monitor_CC-meta | 8 | 8593 | 5 | — | _ |

**classification (manual):** _

### T022 — 1779203353

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | resize cursor menubar panel bottom edge drag | Monitor_CC-meta | 5 | 8790 | 5 | — | _ |

**classification (manual):** _

### T023 — 1779227238
*2 queries — follow-up topic*

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar discover worker_is_working tmux window_activity | Monitor_CC-meta | 5 | 9268 | 5 | — | _ |
| 2 | worker working badge tmux window_activity discover | Monitor_CC-meta | 8 | 13762 | 8 | — | _ |

**classification (manual):** _

### T024 — 1779227238
*4 queries — follow-up topic*

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | cursor rect panel edges resize hover | Monitor_CC-meta | 5 | — | — | — | _ |
| 2 | cursor probe panel cursor rects | Monitor_CC-features | 5 | 20169 | 10 | — | _ |
| 3 | LSUIElement accessory app NSCursor cursor rects activation | Monitor_CC-meta | 3 | 5444 | 3 | — | _ |
| 4 | menubar hover diagnostic logging probe cursor | Monitor_CC-features | 3 | 7531 | 3 | — | _ |

**classification (manual):** _

### T025 — 1779227238

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | claude code hooks settings.json global registration | Monitor_CC-meta | 4 | 13039 | 7 | — | _ |

**classification (manual):** _

### T026 — 1779227238

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | hook antipattern prevention destructive commands | Monitor_CC-features | 3 | — | — | — | _ |

**classification (manual):** _

### T027 — 1779227238

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | gh-cli get_repo_tree 404 anthropics claude-code docs not found | Monitor_CC-features | 3 | 5214 | 3 | — | _ |

**classification (manual):** _

### T028 — 1779236062
*3 queries — follow-up topic*

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | DOCS pattern audit drift documentation structure | Monitor_CC-meta | def | 383 | 0 | — | _ |
| 2 | docs drift whitelist worker policy | Monitor_CC-features | def | — | — | — | _ |
| 3 | DOCS.md pattern drift documentation | Monitor_CC-meta | def | 1117 | 0 | — | _ |

**classification (manual):** _

### T029 — 1779236062

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar hotkey Cmd+L panel toggle keyDown | Monitor_CC-meta | 5 | — | — | — | _ |

**classification (manual):** _

### T030 — 1779236062

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | session row click action focus ghostty foreground | Monitor_CC-meta | 5 | 17132 | 10 | — | _ |

**classification (manual):** _

### T031 — 1779236062

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | cursor edges NSPanel LSUIElement accessory app resize | Monitor_CC-features | 5 | 10025 | 5 | — | _ |

**classification (manual):** _

### T032 — 1779290903

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | menubar sleep timer detection background bash | Monitor_CC-meta | 5 | 8544 | 5 | — | _ |

**classification (manual):** _

### T033 — 1779290903
*2 queries — follow-up topic*

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | hook registry pretooluse bash block validation | Monitor_CC-meta | 5 | 8533 | 5 | — | _ |
| 2 | PreToolUse Bash hook architecture | Monitor_CC-meta | 5 | 17963 | 10 | — | _ |

**classification (manual):** _

### T034 — 1779290903

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | proxy log opus session jsonl structure | Monitor_CC-meta | 5 | — | — | — | _ |

**classification (manual):** _

### T035 — 1779290903

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | rag-cli search_hybrid evaluation truncation | Monitor_CC-features | 5 | 19213 | 10 | — | _ |

**classification (manual):** _

### T036 — 1779290903

| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |
|---|-------|-----------|-------|-------------|--------|-----------|------------|
| 1 | hook migration negative rules tool-use | Monitor_CC-features | 5 | — | — | — | _ |

**classification (manual):** _

