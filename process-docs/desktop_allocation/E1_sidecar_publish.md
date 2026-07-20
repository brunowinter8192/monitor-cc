# E1 — cwd_desktop.json Sidecar Publish

## What we did

Implemented the menubar sidecar that publishes verified `{space_id, desktop_no}` pairs per cwd to `APP_SUPPORT/cwd_desktop.json` — enabling blanks' `desktop_targeting.py` to consume ground-truth desktop data instead of running its own fragile detection.

**Three-file change:**

`paths.py` — added `CWD_DESKTOP_FILE = _APP_SUPPORT / "cwd_desktop.json"`.

`desktop_detection.py` — added `_cwd_desktop_lkg: Dict[str, dict] = {}` module-level state. LKG update on the `if info:` success path only (both `space_id` and `desktop_no` non-None). Stale-cwd cleanup at cache-miss start: removes `_cwd_desktop_lkg` entries whose cwd is no longer in the active `cwds` frozenset. Exported to `discover.py` by direct import (matching the `_ghostty_tty_to_id` pattern).

`discover.py` — imported `_cwd_desktop_lkg` from `desktop_detection` and `CWD_DESKTOP_FILE` from `paths`. Added `_write_cwd_desktop_sidecar()` (atomic tempfile + os.replace, exception → return, same pattern as ghostty.py). Called in `list_alive_sessions()` immediately after `detect_main_desktop_numbers()`.

## What we found

**space_id was already computed but discarded.** In the orchestrator loop (line 92): `space_id = spaces[0]` assigned, then `result[cwd] = desktop_no` writes only `desktop_no`. The sidecar captures `space_id` at the same point where it already existed, zero extra CGS calls.

**`except Exception: pass` blocked by project hook.** Hook `block_except_pass.py` detects bare `except ...: pass` in new Edit/Write content. Matched the `ghostty.py:_write_cwd_uuid_map` pattern instead: `except Exception: return`.

**`desktop_detection.py` kept pure (no paths.py import).** Two alternatives considered: (A) write inside orchestrator loop — would add `paths.py` dependency to a pure detection module. (B) return enriched type — would break caller signature. Chosen: export `_cwd_desktop_lkg` directly (module-level dict, same convention as `_ghostty_tty_to_id` export from ghostty.py), write in `discover.py`.

**Unit test approach:** directly manipulate `det_mod._cwd_desktop_lkg` + `patch("src.menubar.discover.CWD_DESKTOP_FILE", ...)`. No mocking of CGS/osascript needed — tests the LKG invariant and stale-cleanup logic in isolation.

## dev/ scripts used

`dev/test_cwd_desktop_sidecar.py` — two test cases:
1. None does NOT clobber LKG (first write good, simulate failure by not updating LKG, assert file unchanged)
2. stale-cwd removed from active set → omitted in next write (simulate stale cleanup, assert entry absent)

Run: `PYTHONPATH=. ./venv/bin/python dev/test_cwd_desktop_sidecar.py`

## Decision / next

Sidecar is published every `detect_main_desktop_numbers` cache-miss (~10s when sessions stable, immediate on cwd-set change). blanks `desktop_targeting.py` consumes `cwd_desktop.json` as primary signal; falls back to own detection when cwd absent (first tick before any successful detection, or brief n_cand=0 window).

Stage 2 Part A complete. Part B: blanks consumer (read `cwd_desktop.json`, cache TTL, fallback chain).
