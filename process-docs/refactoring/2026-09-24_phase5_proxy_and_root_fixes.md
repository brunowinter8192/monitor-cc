# 2026-09-24 — Phase 5 fixes: proxy stderr, one MONITOR_CC_ROOT resolver, config-swallow traces

Session of worker mcref-flow-b. Task: fix the proxy findings of its own Phase 5 scan (X-STDERR, X1-X6, X8-X16, X19) and the whole X-ROOT cluster (19 sites), following Main's decisions. Five commits on branch `mcref-flow-b`, one per finding group. The scan itself lives outside the repo; the IDs below are only labels.

## Decisions taken with Main before the work

- The resolver is a function, not a constant, so it lives in its own module `src/monitor_root.py` (not in `src/constants.py`, which is the project's config module for shared constants).
- X9: the model-override result stays cached per model id; only the traceability is added. A transient `_load_config` failure that returns `{}` still pins an empty snapshot for that model for the process lifetime.
- X6: a missing `PROXY_LOG_ID` raises at addon import. Only the dev/proxy harness env is adapted for it.
- P06 (`src/proxy_addon.py` bootstrap) is part of the task.

## What changed, by group

1. **Resolver (`src/monitor_root.py`).** `resolve_monitor_cc_root(report, env_var="MONITOR_CC_ROOT")`: env var if non-empty, else the checkout that contains the module (`Path(__file__).parent.parent`, always correct, also inside the proxy live copy because the module is loaded from the checkout); raises `FileNotFoundError` when the directory does not exist; calls `report(root, source)` once per distinct (env var, root, source). `report` is required so the module imports nothing and stays inside the py2app bundle (`setup_py2app.py` includes and `_BUNDLE_SRC_KEEP` got `monitor_root`). Reporters: `monitor_janitor` writes a `ROOT source=... root=...` line to `monitor_sweep.log`; `proxy_display` (one `_monitor_root()` in `forwarded_parser.py`, imported by `parser.py` and `side_logs.py`) and `ram_audit` use `log_pane_note('monitor_root', ...)`; `dual_log_cli/discovery.py` prints `monitor root: ...` and `dual_log dir: ... (branch)` to stderr; the menubar uses `PROJECT_ROOT` through `menubar/root_report.py` (lazy import of `menubar_log`, because `menubar_log` imports `paths`); the proxy uses `proxy/proxy_error_log.py` (`proxy_monitor_root`).
   - `dual_log_cli/discovery.resolve_dual_log_dir` keeps its three observed branches (env root, repo root, main checkout when run inside a worktree, else the unvalidated repo path) and now prints which one won. With the env var set it still returns the env path without an existence check (main then prints the not-found error), exactly as before.
   - `src/proxy_addon.py` now knows exactly two layouts: live shim `src/logs/.proxy_addon_live_<id>.py` next to `.proxy_live_<id>/` (repo root = two levels above the shim), and `src/proxy_addon.py`. It raises when `proxy/` is missing and puts the repo root and the package dir on `sys.path`. The `sys.path` inserts and the `constants` import trick in `payload_helpers`, `rules`, `tools`, `rules_config` are gone; `from src.constants import TOOL_BLOCKLIST` replaces `from constants import ...`.
2. **X-STDERR and X1-X5, X8, X10.** New `proxy/proxy_error_log.py`: `log_proxy_error(source, error_or_text)` appends `[timestamp] [source] <error>` plus traceback to `<root>/src/logs/proxy_error.log` (2 MB cap, keeps 500 KB, its own failure swallowed), `log_proxy_error_on_change`/`clear_proxy_error` for per-request repeats. Every `print(..., file=sys.stderr)` in `src/proxy/` now goes there; the handlers still fail open. Sources carry the flow id for hook handlers, for example `addon.request flow=<id>`.
3. **X6, X14, X15.** `PROXY_LOG_ID` is the only id variable (`proxy_log_id()` in `addon_dual_log.py`); `PROXY_SESSION_ID` is no longer read and there are no unsuffixed dual-log names. A `worker_` id with fewer than 4 parts raises `ValueError`; every other id stays `main` (the observed shapes are `opus_<name>_<epoch>` and `worker_<sid>_<name>_<epoch>`). `_infer_model_family` returns `unknown` for anything that is not haiku/sonnet/opus, and `addon.request` logs an unknown model once per changed model string. `strip_sr._strip_system_reminder` raises `ValueError` for a marker without template.
4. **X9, X11, X12.** `_load_config`, `_read_rule_file`, `_inject_model_override`, `_inject_context_management`, `_load_active_plugins`, `_is_project_excluded`, `_load_schema_store` log to `proxy_error.log` on change and re-arm after a healthy read; return values are unchanged. The legacy branch `_inject_legacy_model_override` and its `kind: legacy` snapshot are deleted, so `_inject_model_override(payload, fixated)` lost its `model_family` parameter (and `_run_post_fixation_pipeline` its `model_family`).
5. **X16, X19.** `bp_count` in `cache._set_cache_breakpoints` removed; `build_message_spans`, `_split_stripped_segments`, `_build_fwd_spans` removed from `diff_engine.py`. `_span_counts` stays (imported by `dev/proxy_dual_log/diff_strip_inject.py`).

## Verification

Baselines were taken on the merged `integration` state before any edit and frozen: a copy of one `_original.jsonl` (`ADDON_HOOK_BYTE_IDENTITY_LOG`, `PROXY_PIPELINE_BYTE_IDENTITY_LOG` point at it; both harnesses otherwise pick the newest log, so their hashes drift over time), `mitmproxy` stubbed by a module on `PYTHONPATH` (the installed mitmproxy is a cask binary, not importable). Compared after every group:

| Harness | Result |
|---|---|
| `dev/proxy/test_strip_fix.py` | 322/322 before and after |
| `dev/proxy/test_role_keyed_rules.py`, `test_sidecar_delta_chain.py`, `dev/proxy_dual_log/test_composition_invariant/` (12 checks), 18 `dev/dual_log_cli/tests/test_*.py`, `dev/pane_error_log/p1_pane_modules.py` | output byte-identical before and after |
| `dev/proxy/pipeline_byte_identity.py` (frozen log) | HASH identical through all five groups |
| `dev/proxy/addon_hook_byte_identity.py` | HASH changed once, on purpose, in group 2: it hashes the captured stderr and the proxy no longer writes to stderr. The hash of the six dual logs alone (script run against the old and the new tree) is identical, `54e29128...`; the 2 former stderr lines are now in `proxy_error.log` (plus one `[monitor_root]` line). New baseline 54e29128... |
| `dev/ram_audit/dump_byte_identity.py` | HASH changed once: exactly one line of the normalized dump differs, `classmethod` gc count 78 to 104, caused by the extra imports (`traceback` via `pane_error_log`). New baseline 84cd08ee... |
| `_inject_context_management` / `_inject_model_override` old vs new | 54 comparisons over 9 configs and 3 payloads, identical |
| `cache.py`, `diff_engine.py` | AST comparison: only the intended functions removed/changed |

Intended behaviour changes are shown by new tests (all run cases as parallel subprocesses): `dev/monitor_root/test_monitor_root.py` (12 cases), `dev/proxy/test_live_copy_bootstrap.py` (5, mirror repo built with the exact copy layout of `claude_proxy_start.sh`), `test_proxy_error_log.py` (12), `test_proxy_env_and_family.py` (6), `test_proxy_config_trace.py` (7).

`dev/native-model-start/p2_model_params_probe.py` (runner of `model_override_injection_tests.py` and `thinking_context_management_tests.py`): 70 PASS before, 60 PASS after, 0 FAIL both; the drop is the deleted legacy checks (Test 1 and Test 10 were rewritten to "legacy-only config is ignored / pins a no-op"). The script ends with an unrelated `FileNotFoundError` for `dev/proxy_dual_log/attribution_coverage.py` both before and after.

## Consequences outside the diff, and gotchas for the next agent

- **Dev scripts that import proxy modules needed the repo root on `sys.path`.** Removing the `sys.path` hack from the proxy modules broke 17 scripts that only inserted `<root>/src`. I added a `sys.path.insert(0, <root>)` line next to their existing insert and compared exit codes before/after over 41 scripts (identical). Scripts that construct or import `proxy.addon` also needed `PROXY_LOG_ID` (`addons = [ProxyAddon()]` runs at import): six got `os.environ.setdefault('PROXY_LOG_ID', 'opus_probe_0')`. Any future dev script that imports `proxy.addon` needs the same.
- **The hash-based proxy janitor fires once.** `claude_proxy_start.sh` computes a hash over `proxy_addon.py` and `src/proxy/`; on a change it purges dual-log files older than 60 minutes at the next proxy start (`.proxy_version`). Expect that once after merging. Running proxies keep their frozen live copy and only get the new code after a restart.
- **Worker proxies must export `PROXY_LOG_ID`.** The live shims present on disk (`.proxy_addon_live_worker_*`) and their dual logs (`api_requests_worker_<sid>_<name>_<epoch>`) show they do; a proxy started without it now fails at import instead of writing unsuffixed files.
- **`/tmp` fallbacks are gone.** With `MONITOR_CC_ROOT` unset the proxy used to write dual logs to `/tmp/dual_log` and `bg_escape_events.jsonl` to `/tmp`; it now resolves the checkout root. The start script always exports the variable, so production paths are unchanged.
- **`unknown` family.** Every model string in the local dual logs (about 3,570 requests in 226 dual-log files) is haiku, sonnet or opus, so no live request reaches the new branch today. A model id outside those three now gets its own state bucket (rules apply like opus: not haiku) and one `addon.model_family` line in `proxy_error.log`.
- **`proxy_error.log` name.** `claude_proxy_start.sh` deletes `proxy_errors_*.log` (legacy pattern); the new file is `proxy_error.log` on purpose.
- **Menubar layout.** `menubar/paths.py` cannot import `menubar_log` at top level (`menubar_log` imports `paths`); hence `root_report.py` with a function-level import.
- **Side effect of my verification scans.** To compare exit codes over dev scripts I ran the scripts that mention `MONITOR_CC_ROOT` (31 scripts) in a temp copy; that list included `dev/session_launcher/t2_launch_tab.py` and `dev/pane_flicker/*`. Both exited 1 before and after (unchanged), but I did not check beforehand what they touch at runtime.
- **Not mine:** `dev/proxy/DOCS.md` lists `test_strip_fix_fixtures.py` as 83 LOC; the file has 92. Untouched.

## Left open

- Amplifier (a) of X9 stays by decision: a transient empty config at the first request of a model freezes a no-op for that model for the whole proxy session, now visible as a `rules_config.load_config` line but not self-healing.
- `_load_active_plugins` and `_is_project_excluded` read their files on every request; only the log side is deduplicated.

## Merge of integration (later the same day)

Conflicts in `setup_py2app.py`, `src/proxy_display/{forwarded_parser,parser,side_logs}.py` and four DOCS.md files. Integration had rewritten the three proxy_display modules (missing-marker note, `get_proxy_session_start_ts` returning `None`, `JsonlReader`, required arguments of `scan_worker_errors_logs`) and removed the `setup_py2app` comment block. Resolution: take integration's version of each file and re-apply only the root resolution (`_monitor_root()` from `forwarded_parser`, `monitor_root` in the py2app includes and `_BUNDLE_SRC_KEEP`). `_resolve_log_id` keeps integration's `root: str` signature because `dev/proxy_display/test_forwarded_tripwires.py` calls it with a string. `dev/monitor_root/test_monitor_root.py` now filters the pane notes for `monitor_root`, since integration's parser also notes a missing marker. Hashes after the merge equal the earlier baselines (hook 54e29128..., pipeline 59a043de..., ram 84cd08ee...).
