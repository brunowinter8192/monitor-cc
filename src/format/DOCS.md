# src/format/

## Role

Side-effect-free ANSI string rendering for the tokens/cache-tracker pane, plus a proxy-strip highlight helper reused by the warnings pane. Touch to change how the cache tracker renders; not for I/O, shared state or pane loop logic.

## Public Interface

`__init__.py` re-exports the cache-tracker formatter and two small formatting helpers from `token_format.py`. The strip highlight helper is imported directly from `strip_marker.py`.

## Flow

Cache-turn lists and pane geometry (from the calling pane) -> `token_format.py` builds logical lines and the scroll viewport, reusing `turn_cache.py` for frozen per-turn rendering -> the pane applies zebra, hover and truncation in its own row loop.

## Modules

### strip_marker.py (20 LOC)

**Purpose:** highlights found proxy-strip chunks inside a text, line by line.
**Reads:** chunk strings passed as arguments.
**Writes:** returns strings only.
**Called by:** `panes/warnings_render.py`.
**Calls out:** none.

---

### token_format.py (350 LOC)

**Purpose:** builds the logical lines, sticky header and scroll viewport of the tokens/cache-tracker pane, plus shared request numbering and time helpers.
**Reads:** cache-turn lists, expand states, pane dimensions, scroll offset and optional search or response data, all passed as arguments.
**Writes:** returns a tuple of viewport data; fills a caller-supplied navigation dict in place.
**Called by:** `panes/token_pane.py`, `workers/worker_tokens_pane.py`, `panes/token_search.py`, `proxy_display/format.py`, `proxy_display/frozen_turns.py`, `dual_log_cli/numbering.py`.
**Calls out:** none.

---

### turn_cache.py (170 LOC)

**Purpose:** frozen-turn cache for the cache tracker; re-renders only turns whose render inputs changed and republishes the navigation map.
**Reads:** the cache dict, turns and render-input bundle passed by `token_format.py`.
**Writes:** mutates the passed cache dict and navigation dict in place.
**Called by:** `format/token_format.py`; the cache dict is owned by `panes/token_pane.py` and `workers/worker_tokens_pane.py`.
**Calls out:** none.

---
