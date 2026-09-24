# dev/pipeline/

## Role
Standalone measurement scripts that profiled memory growth, filesystem call cost, parsing overhead and message-type coverage of the core monitor pipeline, feeding early design decisions. Touch only when re-measuring one aspect against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Each script is its own entry point: `python3 dev/pipeline/<subdir>/<script>.py`.

## Flow
Each script scans real session JSONL files under the user's Claude Code projects directory (one measures all files, the others the newest). Each measures one aspect and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Sub-directories

- `memory_profile/`: Measures tool-call cache growth of the monitor pipeline by replaying the newest session in batches. See its own `DOCS.md`.
- `io_profile/`: Counts filesystem calls per poll cycle of the session finder. See its own `DOCS.md`.
- `parsing_profile/`: Times each session-JSONL extract function to measure multi-pass parsing overhead. See its own `DOCS.md`.
- `format_stability/`: Scans all session JSONL files for top-level and content-block types outside a known set. See its own `DOCS.md`.

## State
None. The path-method patching in the poll-cost script is restored before its cycle function returns.
