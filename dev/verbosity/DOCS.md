# dev/verbosity/

## Role
Holds analysis of redundancy in this assistant's own chat output, adapting a process-efficiency
measurement (originally applied to LLM solution-rounds) to Opus turn-exchanges, plus the frozen
extraction the analysis was run against. `extract_turns.py` produces the corpus only — the
distinctness clustering itself is a manual, per-exchange semantic judgment against a fixed criterion,
not a reusable pipeline; a future pass over new turns needs a fresh manual read, not a re-run of code.

## Flow
`extract_turns.py` reads real session JSONL files, reconstructs Opus turns, and writes numbered
exchanges to a fixed scratch path. The frozen corpus and its manual clustering live under `corpus/`
and `md/` respectively, checkable end to end without depending on `/tmp`.

## Modules

### extract_turns.py (42 LOC)

**Purpose:** Reads session JSONL files, reconstructs Opus turns (one user message followed by
consecutive Opus-model assistant text blocks), splits each turn's text into numbered exchanges on
bold-point/stop-emoji lines, keeps only turns with 4+ exchanges, and writes the result.
**Reads:** session JSONL files under the user's Claude Code projects directory (hardcoded path, not a
CLI argument).
**Writes:** a fixed scratch path under the system temp directory (hardcoded, not a CLI argument).
**Called by:** none — manual CLI. Produced the frozen `corpus/k2_turns.md` on one run; re-running
reads the live (further-grown) session files, not the frozen `corpus/sessions/` copies.
**Calls out:** none — stdlib JSONL parsing only.

---

## Gotchas
- `corpus/sessions/*.jsonl` and `corpus/k2_turns.md` are frozen snapshots, not regenerated on every
  run — `extract_turns.py`'s source path is hardcoded to the live session directory, so a fresh run
  is not guaranteed to reproduce the same turns byte-for-byte. Do not re-run to "refresh" the corpus
  without a new dated report; the existing report's tables are checked against the specific frozen
  files committed here.
- `corpus/sessions/*.jsonl` are full session transcripts (tool calls + output, not just prose) and
  were scanned for credential material before committing — targeted patterns (cloud/API keys, private
  key headers, `.env`-style assignments, basic-auth-in-URL, SSH keys, certificate headers) plus a
  high-entropy-string sweep found zero credential material; the only base64 blobs present are Claude's
  own extended-thinking signature tokens and pasted-screenshot image data.
