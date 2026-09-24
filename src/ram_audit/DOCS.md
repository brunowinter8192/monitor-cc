# src/ram_audit/

## Role

Pane instrumentation for RAM diagnostics: a single helper each pane calls once at loop entry so the running process answers a signal by writing a memory snapshot file. Touch to add RAM profiling to a new pane or change the dump format; not for normal pane logic.

## Public Interface

`__init__.py` re-exports the registration helper from `instrument.py`; panes call it once at run-loop entry.

## Flow

Pane registers at startup -> a manual or scripted `kill -USR1 <pid>` (see `dev/ram_audit/`) -> the handler assembles RSS, gc, tracemalloc and pane-state sections -> one text file per dump under `dev/ram_audit/dumps/`.

## Modules

### instrument.py (106 LOC)

**Purpose:** shared RAM-dump helper: tracemalloc start, PID file, signal handler registration and dump-file writer.
**Reads:** the pane's module-state provider callback; process RSS.
**Writes:** a PID file under `/tmp`, removed on exit; dump files under `dev/ram_audit/dumps/`.
**Called by:** `panes/token_pane.py`, `panes/warnings_pane.py`, `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `workers/worker_tokens_pane.py`.
**Calls out:** `psutil` (optional RSS source).

---
