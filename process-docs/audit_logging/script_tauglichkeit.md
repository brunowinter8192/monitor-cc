# Script Suitability — dev/hook_firing/ + dev/tool_use_errors/ (2026-05-24)

**Question:** which of the existing dev scripts retain their value once the two new
logs (`src/logs/hook_firing.jsonl`, `src/logs/tool_errors.jsonl`) are live?

**Methodology:** decompose each script into functional units, check each one against
the new data basis individually. Three verdict categories: KEEP (function valuable
independent of the new data basis), REPLACE (function replaceable by a one-line
`jq`/`grep`), EVOLVE (code value present, but the data source changes — re-implementing
on the new basis makes sense).

Re-eval happens only AFTER the log build — this assessment is a forward-looking
hypothesis. The actual decision follows from live data.

---

## dev/hook_firing/analyze.py (398 LOC)

### Functional Units

| Block | LOC | What it does | Suitability post-logs |
|---|---|---|---|
| Pass 1: uuid_map + tool_use_id_map build | ~30 | Iterates CC session JSONLs, builds indices to map BLOCKED events to their triggering command | **REPLACE** — hook_firing.jsonl has the command directly in the event, no mapping needed |
| Pass 2: BLOCKED regex extraction | ~35 | Greps `"PreToolUse:<Tool> hook error: ... BLOCKED:"`, parses hook name + reason | **REPLACE** — log has `hook`, `decision`, `reason` as fields |
| `_find_trigger` fallback (parentUuid) | ~15 | When tool_use_id doesn't resolve, falls back to parent-message-first-tool_use | **REPLACE** — fallback unnecessary, log always contains the command directly |
| `_classify_fp` per-hook FP/TP heuristics | ~60 | Per-hook (7 hooks covered): regex checks for `_LOOP_RE`, `_SIDE_EFFECT_RE`, sleep numerics, heredoc-in-$() gap, etc. | **KEEP/EVOLVE** — encoded domain knowledge, each heuristic is a genuine finding from prior sessions |
| Friction-cluster detection | ~25 | Temporal clustering (≥3 blocks from the same hook/project/branch in a 30min window) | **KEEP/EVOLVE** — data-source-agnostic, only needs the (ts, hook, project, branch) tuple present in the new log |
| Report building (MD output) | ~80 | Per-hook summary, top-trigger patterns, events table | **EVOLVE** — structure stays, renderer input shifts from events-list-from-regex to events-list-from-jsonl |
| Project-from-cwd derivation | ~10 | Strips worktree path | **KEEP** — helper, data-source-agnostic |
| CLI args (--since, --project, --hook, --output) | ~25 | argparse | **KEEP** — user-facing interface stays useful |
| File-traversal infrastructure | ~30 | `PROJECTS_DIR.glob`, mtime pre-filter | **REPLACE** — a single JSONL instead of N session JSONLs, no glob needed |

### Net Suitability

| Verdict | LOC | Share |
|---|---|---|
| KEEP (reusable verbatim) | ~35 | 9% |
| EVOLVE (good logic, new data source) | ~165 | 41% |
| REPLACE (replaceable via jq, code obsolete) | ~110 | 28% |
| Boilerplate / glue | ~88 | 22% |

**Initial proposal:** REWRITE instead of DELETE. New script ~150 LOC (vs 398 today),
using `src/logs/hook_firing.jsonl` as input, keeping the `_classify_fp` heuristics + the
friction-cluster detection + the report structure. Keeps the name `analyze.py`,
replacing the old file.

**Alternative considered:** DELETE entirely, FP classification via an ad-hoc grep
cookbook in the README. Works but loses the 60 LOC of encoded heuristics — the user
would have to reconstruct them from memory each time ("is `sleep 3 && launchctl ...` an
FP because ≤5s settling, or a TP because it's in a loop?"). Domain-knowledge loss.

This initial recommendation was superseded — see "Correction" below.

---

## dev/tool_use_errors/analyze.py (397 LOC)

### Functional Units

| Block | LOC | What it does | Suitability post-logs |
|---|---|---|---|
| Proxy-JSONL parse + tool_use/tool_result collection | ~50 | Loads `raw_payload`, collects tool_use blocks deduped by id, collects tool_result blocks deduped by tool_use_id | **REPLACE** — tool_errors.jsonl has extracted errors directly, no raw-payload navigation needed |
| `_build_pairs` (tool_use ↔ tool_result via id) | ~30 | Links the two maps | **REPLACE** — the log already persists the pairing |
| 18 signature patterns + lambda predicates | ~95 | Pattern library: `_HOOK_BLOCK_RE`, `_GIT_AMBIG_RE`, `_PARALLEL_TAG`, ... 18 patterns total | **EXTRACT-AS-COOKBOOK** — the value is the pattern regexes themselves, not the script machinery around them |
| `_run_sigs` evaluation loop | ~25 | Per pair: tries all 18 patterns, takes the first match | **REPLACE** — `jq + grep` over tool_errors.jsonl does the same |
| Hookability-bucket grouping | ~20 | 6 buckets, sorted by priority | **EXTRACT-AS-DOC** — the bucket classification is conceptual documentation, no code value |
| Report building (MD output) | ~120 | Hookability-grouped findings, top-error-patterns, uncategorized-patterns | **REPLACE** — `jq \| sort \| uniq -c \| sort -rn \| head` is equivalent |
| CLI args (proxy_jsonl positional, --input-glob, --output) | ~25 | argparse + glob expansion | **REPLACE** — no glob needed, single log file |
| Log-label derivation (opus / worker:<name>) | ~10 | Filename parsing | **EXTRACT-AS-LOGIC** — worker attribution is needed in the log writer (Phase 1) anyway, same logic |

### Net Suitability

| Verdict | LOC | Share |
|---|---|---|
| EXTRACT-AS-COOKBOOK (pattern defs as doc) | ~115 | 29% |
| EXTRACT-AS-LOGIC (build into log writer) | ~10 | 3% |
| REPLACE (directly replaceable via jq) | ~220 | 55% |
| Boilerplate / glue | ~52 | 13% |

**Initial proposal:** DELETE script + DOCS. Move the 18 pattern definitions into a
cookbook — per pattern: name + regex/tag + example jq command against
tool_errors.jsonl. A cookbook is statically maintainable, no code maintenance, ad-hoc
`jq -f cookbook/<pattern>.jq` usable directly.

The worker-attribution logic (`_log_label`) moves into the tool-error-log writer
(Phase 1 implementation) — needed there anyway.

---

## Summary (Final 2026-05-24)

| Script | Verdict | Rationale |
|---|---|---|
| `dev/hook_firing/analyze.py` | **DELETE** | The meta-FP problem (see below) outweighs the domain-knowledge value of the heuristics. Heuristics moved into a historical catalog as archive. |
| `dev/tool_use_errors/analyze.py` | **DELETE** | 55% of code replaceable via jq + the meta-FP problem. 18 pattern definitions moved into the historical catalog. |
| `dev/hook_firing/DOCS.md` | **DELETE** | Follows the script. |
| `dev/tool_use_errors/DOCS.md` | **DELETE** | Follows the script. |
| `dev/hook_firing/reports/*` | **KEEP** | Historical snapshot artifacts with concrete dated findings. |
| `dev/tool_use_errors/reports/*` | **KEEP** | Same as above. |
| `dev/sleep_pattern_analysis/` | **KEEP** | Audit run complete, evidence for the `rewrite_chained_sleep.py` design. |
| `dev/hook_smoke/` | **KEEP + EXTEND** | Smoke tests active, gaining new tests for the two logs. |

## Correction of the Initial Recommendation

The initial LOC breakdown above recommended REWRITE for `hook_firing/analyze.py` based
on the ~60 LOC of encoded FP heuristics. That recommendation was overturned by user
feedback: hooks are generally non-trivial, and scripting the analysis doesn't make
sense because the analysis then has just as many FPs as the hooks themselves — the
prior approach was judged not good enough to keep.

**Meta-FP problem:** a script that classifies hook fires is itself a second layer of
heuristic logic on top of the first (the hooks). Both layers have their own FP rates.
The analysis FPs obscure the hook FPs — debugging then means untangling two heuristic
layers in parallel instead of one.

The per-hook heuristics in `_classify_fp` are genuine knowledge — but more valuable as
**documented knowledge** in a catalog than as **maintained code**. In code form they
must be kept in sync per hook update; in doc form they are a static reference the
implementer reads and applies mentally while building a probe hook.

The asymmetry between the two scripts (hook_firing REWRITE vs tool_use_errors DELETE)
was resolved this way — both DELETE.

**Re-eval trigger:** moot. The workflow shift (script-driven → human-in-the-loop with
grep + heredoc + probe hooks) is the final direction, no longer a hypothesis.
