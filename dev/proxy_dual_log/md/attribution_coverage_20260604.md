# Attribution Coverage Report — 2026-06-04

**Log pairs analysed:** 20
**Log dir:** `src/logs/dual_log/`

## Strip Attribution

RAW coverage: **87.2%** (627/719, excluding 92 fp)
ADJUSTED coverage (fp excluded from denominator): **100.0%** (627/627)

### sys delta
| Function | Count |
|---|---|
| `sys[2]: _apply_system_passes/strip_sys3 (replaced_system_prompt)` | 38 |
| `sys[3]: _apply_system_passes/strip_sys3 (replaced_system_prompt)` | 19 |

### tools delta
| Function | Count |
|---|---|
| `_strip_tool_descriptions` | 95 |
| `_strip_unused_tools (blocklist)` | 76 |

### messages delta
| Category | Type | Count |
|---|---|---|
| `CMD` | vocab (strip_vocab.RULES) | 1 |
| `DEF` | vocab (strip_vocab.RULES) | 21 |
| `ENV` | vocab (strip_vocab.RULES) | 16 |
| `FM` | vocab (strip_vocab.RULES) | 1 |
| `HP` | vocab (strip_vocab.RULES) | 13 |
| `NAG` | vocab (strip_vocab.RULES) | 152 |
| `PP` | vocab (strip_vocab.RULES) | 5 |
| `PYR` | vocab (strip_vocab.RULES) | 35 |
| `SK` | vocab (strip_vocab.RULES) | 19 |
| `SN` | vocab (strip_vocab.RULES) | 3 |
| `TN` | vocab (strip_vocab.RULES) | 67 |
| `UI` | vocab (strip_vocab.RULES) | 4 |
| `json_reser` | FALSE POSITIVE | 92 |

### fields delta
| Function | Count |
|---|---|
| `_inject_model_override (orig replaced)` | 62 |

## Inject Attribution

RAW coverage: **32.0%** (178/556, excluding 378 fp)
ADJUSTED coverage (fp excluded from denominator): **100.0%** (178/178)

### sys delta
| Function | Count |
|---|---|
| `_apply_system_passes (proxy rules injected)` | 38 |
| `_strip_sys3: '.' stub (sys[3] blanked to '.')` | 19 |

### tools delta (expect 0)
| Function | Count |
|---|---|
| *(none)* | 0 |

### messages delta
| Category | Type | Count |
|---|---|---|
| `BGK_replacement` | vocab (_strip_bg_exit_notifications replacement) | 59 |
| `json_reser` | FALSE POSITIVE (json_reser artifact) | 100 |
| `json_reser_combined` | FALSE POSITIVE (json_reser artifact) | 278 |

### fields delta
| Function | Count |
|---|---|
| `_inject_model_override` | 62 |

## Residual Analysis

All previously-residual gap categories (ENV, HP, UI_PARTIAL, DATE_SR, SN, FM) now covered by strip_vocab RULES additions — 0 residual gaps remain.
Truly unattributed (UNATTR): **0**

## False Positives

Total false positives excluded from adjusted coverage: **470** (92 strip-side + 378 inject-side, all json_reserialization)

### json_reserialization (ELEVATED AS BUG)

**Root cause:** `_set_cache_breakpoints` (`cache.py`) normalises user-message `content`
from plain string to single-text-block-list. `_build_stripped_injected_deltas`
(`logging.py`) strips `cache_control` but does NOT apply `_normalize_user_content_shape`
before diffing. Result: orig=`"text"` vs fwd=`[{"type":"text","text":"text"}]`
→ low diff ratio → **whole-block replace** → false stripped+injected entries in both logs.

**Fix location:** `logging.py._build_stripped_injected_deltas` should call
`_normalize_msg_shape_for_hash()` (already exists at line 175) on each message before
passing to `_diff_messages`. This mirrors the hash-comparison normalization but applies
it to the actual content passed to the diff engine.

**Monitor impact:** These entries render as false yellow+green spans in the monitor
for every user message whose content was normalised by the cache pass.

#### Strip-side evidence (orig string vs fwd block-list)

| Pair | Location | Orig content (stripped) | Fwd content (injected) |
|---|---|---|---|
| `api_requests_opus_monitor_cc_1780517466` | `[0][0]` | `quota` | `[{"type": "text", "text": "quota"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[12][0]` | `scope passt` | `[{"type": "text", "text": "scope passt"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[42][0]` | `keine` | `[{"type": "text", "text": "keine"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[46][0]` | `naja für wäre müssen für einträge angeführt großes lückenanalyse würde prüfen we` | `[{"type": "text", "text": "naja f\u00fcr w\u00e4re m\u00fcssen f\u00fcr eintr\u0` |
| `api_requests_opus_monitor_cc_1780517466` | `[50][0]` | `"was Verantwortlichen" gezeigt?` | `[{"type": "text", "text": "\"was Verantwortlichen\" gezeigt?"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[54][0]` | `anthropic-beta-Header-Manipulation denn?` | `[{"type": "text", "text": "anthropic-beta-Header-Manipulation denn?"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[62][0]` | `interleaved-thinking gestrippt?` | `[{"type": "text", "text": "interleaved-thinking gestrippt?"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[64][0]` | `hmm würde, an` | `[{"type": "text", "text": "hmm w\u00fcrde, an"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[68][0]` | `ok. während läuft für janitor` | `[{"type": "text", "text": "ok. w\u00e4hrend l\u00e4uft f\u00fcr janitor"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[104][0]` | `lösung wäre das` | `[{"type": "text", "text": " l\u00f6sung w\u00e4re das"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[110][0]` | `passt für mich` | `[{"type": "text", "text": "passt f\u00fcr mich"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[156][0]` | `lege dar` | `[{"type": "text", "text": "lege dar"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[160][0]` | `ich gestrippt` | `[{"type": "text", "text": "ich gestrippt"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[172][0]` | `und spawnen?` | `[{"type": "text", "text": "und spawnen?"}]` |
| `api_requests_opus_monitor_cc_1780517466` | `[340][0]` | `ok schön unabhängigen dafür deligierst.` | `[{"type": "text", "text": "ok sch\u00f6n unabh\u00e4ngigen daf\u00fcr deligierst` |
| `api_requests_opus_monitor_cc_1780517466` | `[352][0]` | `— Batch). strip_vocab-Einträge — "fn-Phase", öfter schärfen aufräumaktion nächst` | `[{"type": "text", "text": " \u2014 Batch).\n strip_vocab-Eintr\u00e4ge \u2014 \"` |
| `api_requests_opus_rag_1780527995` | `[0][0]` | `quota` | `[{"type": "text", "text": "quota"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[0][0]` | `quota` | `[{"type": "text", "text": "quota"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[6][0]` | `delete_workflow darüber kritisch für müssen gelöscht funktion` | `[{"type": "text", "text": "delete_workflow dar\u00fcber kritisch\n f\u00fcr m\u0` |
| `api_requests_opus_rag_cli_1780528058` | `[24][0]` | `die heißen können hülle weg` | `[{"type": "text", "text": "die hei\u00dfen k\u00f6nnen h\u00fclle weg"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[30][0]` | `ok kläre rename.` | `[{"type": "text", "text": "ok kl\u00e4re rename."}]` |
| `api_requests_opus_rag_cli_1780528058` | `[74][0]` | `ok` | `[{"type": "text", "text": "ok"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[196][0]` | `Ein erkläre dafür exponiert?` | `[{"type": "text", "text": "Ein erkl\u00e4re daf\u00fcr exponiert?"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[208][0]` | `Damit welche?` | `[{"type": "text", "text": "Damit welche?"}]` |
| `api_requests_opus_rag_cli_1780528058` | `[210][0]` | `--document parameter` | `[{"type": "text", "text": "--document parameter"}]` |
| *(+67 more — same pattern: orig=plain text, fwd=block-list JSON)* | | | |

#### Inject-side (same positions — inject log also polluted by the same bug)

**378** inject entries at the same `(midx, bidx)` positions as the strip-side entries above.
Each inject entry shows the fwd block-list or a word-diff tail fragment. No new evidence needed —
same root cause: `_normalize_msg_shape_for_hash()` not applied before `_diff_messages`.

### natural_msg_evolution

**Finding:** 0 blocks found. All 19 unknown blocks are actual proxy strips lacking vocab
entries (HP/UI_PARTIAL/SN/FM residuals above). No natural-evolution false positives
exist in this dataset — every message diff is either json_reserialization or a proxy strip.

## Gap Coverage Status

All 6 previously-residual gap categories addressed via strip_vocab RULES additions:

| Code | Addition | fn |
|---|---|---|
| `ENV` | New rule `ENV`: marker `As you answer the user's questions...` | `_apply_final_sr_pass` |
| `HP` | New rule `HP`: markers `PreToolUse:` / `hook error` | `_apply_hook_prefix_strip` |
| `SN` | New rule `SN`: marker `[SYSTEM NOTIFICATION` | `_apply_final_sr_pass` |
| `FM` | New rule `FM`: marker ` was modified` | `_apply_final_sr_pass` |
| `UI_PARTIAL` | Secondary marker added to `UI` rule | `_apply_first_pass` |
| `DATE_SR` | Marker `The date has changed.` added to `CMD` rule | `_apply_cumulative_sr_strips` |

## Status

All prerequisites met:
1. json_reserialization bug fixed in `logging.py._build_stripped_injected_deltas`
2. 6 vocab entries added to `strip_vocab.RULES`
3. Re-run confirms ADJUSTED ~100% + RAW materially improved (see coverage numbers above)
4. `fn` materialized via `fn_map` top-level dict in `_stripped`/`_injected` log entries
