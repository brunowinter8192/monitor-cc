# Cache Rebuild Case Catalog

Cache rebuilds have multiple root-cause families — document each case in `decisions/cache_rebuild_cases.md`:

- **Proxy dead** (wise2627 REQ#5 2026-04-12): mitmdump process crashed, CC used default 5min TTL, 18min gap → full cache loss (CR=0). Fix: infrastructure.
- **Proxy hot-reload after merge**: state reset in `ProxyAddon.prev_messages_by_model` → BP3 can't find unchanged prefix. Fix: live-copy of full proxy package (done).
- **Byte diff in msg content**: e.g. `list1[text+cc] → str` shape demotion when CC moves BP4 forward. NOT always catastrophic (1/11 in monitor_cc session 2026-04-12). Fix: shape normalization in `cache.py` (done 0f847b0).
- **Rule-file edit during active session** (monitor_cc REQ#108+109 2026-04-12): editing any file in `~/.claude/shared-rules/global/` or `proj_monitor/` during a live session changes mtime → proxy rule loader reloads → sys[2] or msg[0] project_rules bytes change → full prefix invalidation. Fix planned: session-state fixation (Bead Monitor_CC-dye).
- **Server-side eviction**: observed at monitor_cc REQ#33 — BP2 missed despite byte-identical `tools_bytes_hash`. Outside proxy control.
- **Tool-marker movement on growth** (monitor_cc REQ#14 2026-04-13, Case 5): old BP2 placement always moved the `cache_control` marker to the current last tool. Adding new tools (e.g. via plugin activation) shifted the marker forward, changed the byte content of the old marker position (marker attribute removed), and pushed the old cache write to exactly the 20-block lookback edge → full rebuild. Fix: `cache.py` BP-layout v2 — Tools Anchor + Tools End two-marker layout (commit `060ff07`).

See `src/proxy/DOCS.md` "Cache-Rebuild Investigation Pattern" for the forensic workflow, and `verify-before-execution.md` "Correlation Check Before Root-Cause Claim" for the falsification discipline.
