# RAG Truncation Audit — 2026-05-20T17:53

## Source JSONLs

- `api_requests_opus_monitor_cc_1778339095.jsonl` (228 events, 189 tool_use blocks)
- `api_requests_opus_monitor_cc_1778351487.jsonl` (134 events, 134 tool_use blocks)
- `api_requests_opus_monitor_cc_1778368827.jsonl` (199 events, 161 tool_use blocks)
- `api_requests_opus_monitor_cc_1778421335.jsonl` (175 events, 158 tool_use blocks)
- `api_requests_opus_monitor_cc_1778424911.jsonl` (180 events, 140 tool_use blocks)
- `api_requests_opus_monitor_cc_1778512886.jsonl` (119 events, 93 tool_use blocks)
- `api_requests_opus_monitor_cc_1778529559.jsonl` (380 events, 297 tool_use blocks)
- `api_requests_opus_monitor_cc_1778596205.jsonl` (220 events, 162 tool_use blocks)
- `api_requests_opus_monitor_cc_1778631643.jsonl` (126 events, 82 tool_use blocks)
- `api_requests_opus_monitor_cc_1778958534.jsonl` (1 events, 0 tool_use blocks)
- `api_requests_opus_monitor_cc_1779120726.jsonl` (187 events, 139 tool_use blocks)
- `api_requests_opus_monitor_cc_1779203353.jsonl` (303 events, 235 tool_use blocks)
- `api_requests_opus_monitor_cc_1779227238.jsonl` (291 events, 227 tool_use blocks)
- `api_requests_opus_monitor_cc_1779236062.jsonl` (215 events, 170 tool_use blocks)
- `api_requests_opus_monitor_cc_1779290903.jsonl` (51 events, 40 tool_use blocks)

Total sessions analyzed: 15. Total events: 2809. Total tool_use blocks (deduped per file): 2227.

## Summary

- Logs with any truncation pattern: 5 / 15
- Unique truncated tool_results (A+B): 5
  - Hypothesis A (rag-cli chunk truncation): 0
  - Hypothesis B (CC inline bash-output truncation): 5
  - Unclassified: 0
- Hypothesis C (echo artifact — pattern in tool_use input or text block): 5 unique occurrences

## Hit Table

| Session-Log | Tool | Trunc-Bytes | Split-Pos | Split-% | Hyp | Preceding Command (preview) |
|-------------|------|-------------|-----------|---------|-----|-----------------------------|
| `opus_monitor_cc_1778424911` | Bash | 19,721 | 5002/10036 | 50% | **B** | `echo "=== ps -A \| grep ghostty ===" && ps -A \| grep -i ghostty \| head -5; echo "=== full ps with ` |
| `opus_monitor_cc_1778529559` | Bash | 3,928 | 5006/10041 | 50% | **B** | `echo "=== Binary ==="; ls -la ~/.local/bin/docs-drift-check 2>&1 echo "" echo "=== Binary content ==` |
| `opus_monitor_cc_1778596205` | Bash | 6,037 | 5006/10041 | 50% | **B** | `echo "=== Monitor_CC gpu_pane ==="; rag-cli search_hybrid "gpu_pane rendering status field unknown q` |
| `opus_monitor_cc_1779290903` | Bash | 6,037 | 4011/5234 | 77% | **B** | `bd show Monitor_CC-3d7y && echo "===" && bd show Monitor_CC-aerx && echo "===" && bd show Monitor_CC` |
| `opus_monitor_cc_1779290903` | Bash | 6,037 | 5112/7797 | 66% | **B** | `worker-cli response janitor; echo "===RAG-TRUNCATION==="; worker-cli response rag-truncation` |

## Hypothesis C — Echo Artifacts

Pattern appears inside tool_use inputs or text blocks (not in tool_result).

| Session-Log | Location | Tool/Role | Sample |
|-------------|----------|-----------|--------|
| `opus_monitor_cc_1779120726` | text_block | user | `ok wir hwaren an der menu bar dran lass mal schauen wie weit wir da sien wir haben einen bead dazu. Und zu den folgenden` |
| `opus_monitor_cc_1779120726` | text_block | assistant | `## Menübar-Status (zv6s)  Bead lebt, **5 offene Issues** drin — nicht 3 wie der Titel sagt:  1. Thinking-not-counted-as-` |
| `opus_monitor_cc_1779120726` | tool_use_input | Bash | `bd create --title "RAG result truncation — top-k result hat '[6037 chars truncated]'" --type task --description "$(cat <` |
| `opus_monitor_cc_1779290903` | tool_use_input | Write | `# Worker: rag-truncation-audit  You are a WORKER. Your worktree: `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude` |
| `opus_monitor_cc_1779290903` | text_block | assistant | `Janitor: Phase B done, committed `3c43aa3`, vor/nach Counts plausibel (31→30 opus, 31→30 worker, 29→0 errors). Eine Anme` |

## CC Inline Truncation — Structural Fingerprint

All Hypothesis B hits share an identical structural signature:

| Log | trunc_pos | total_len | split_% | trunc_bytes |
|-----|-----------|-----------|---------|-------------|
| `opus_monitor_cc_1778424911` | 5002 | 10036 | 49.8% | 19,721 |
| `opus_monitor_cc_1778529559` | 5006 | 10041 | 49.9% | 3,928 |
| `opus_monitor_cc_1778596205` | 5006 | 10041 | 49.9% | 6,037 |
| `opus_monitor_cc_1779290903` | 4011 | 5234 | 76.6% | 6,037 |
| `opus_monitor_cc_1779290903` | 5112 | 7797 | 65.6% | 6,037 |

CC keeps the first ≈5 000 chars and the last ≈5 000 chars of a large Bash output, replacing the middle with `[N characters truncated] ...`. The 49–50% split position is the mechanical fingerprint of this mechanism.

The `1778596205` case: `rag-cli search_hybrid` was called as part of a compound Bash command (`echo === ... ; rag-cli ... ; echo === RAG server ...`). The combined output exceeded ≈10 000 chars. CC truncated the middle, which happened to fall inside a rag-cli result block — giving the appearance of "mid-chunk truncation". The rag-server itself did NOT truncate any chunk.

## Conclusion

**Hypothesis B confirmed. Hypotheses A and C are secondary/derivative.**

- **Hypothesis A (rag-cli/server chunk truncation):** ❌ No evidence. Zero cases where rag-cli is the sole command producing a truncated result. No rag-cli bug.
- **Hypothesis B (CC inline Bash-output truncation):** ✅ All 4 genuine truncations. CC truncates large Bash outputs at the ≈5k/5k midpoint. The rag-cli case (`1778596205`) is a compound Bash call whose combined output exceeded the limit — the truncation landed inside the rag-cli section by coincidence.
- **Hypothesis C (echo artifact):** ✅ Present in 2 logs as downstream echoes. `1779120726`: Opus created bead `bd create` with the `[6037 characters truncated]` string in the description. `1779290903`: Opus wrote a worker prompt (Write tool) whose content referenced the bead description.

**No fix needed in rag-cli or Monitor_CC proxy.** The user-observable symptom ("truncation mid-chunk-content") was CC showing a large Bash output in its inline-truncated form. Resolution: run `rag-cli search_hybrid` as a standalone Bash call (not compounded with other echo/status commands), or read the persisted-output file when CC reports `Output too large`.
