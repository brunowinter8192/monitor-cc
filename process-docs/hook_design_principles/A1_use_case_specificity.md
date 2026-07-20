# A1 — Hook Design Principle: Use-Case-Specificity Over Generality (2026-05-28)

**Status:** design principle, established after a spillover incident in this session.

## Principle

Hooks MUST be written extremely use-case-specific, NEVER general. Generic hooks produce spillover bugs that can't be estimated at build time — what is a "correctly blocked anti-pattern" today can block a legitimate workflow in two weeks once the tool surface has expanded.

Concretely, that means:

1. **Pattern-match on the exact anti-pattern signature**, not on surrounding context. If, for example, a hook should block `sleep N` in the background, match only on `run_in_background=true + sleep + numeric argument`. NOT on "background + anything".

2. **Allow-list before block-list.** If it's clear which patterns are OK, whitelist them explicitly. If it's only clear which patterns are NOT OK, block narrowly and let everything else through.

3. **No tool-class-wide wrapping.** A hook that intercepts and transforms ALL Bash calls is by definition too general. Hooks must operate at the granularity of individual command patterns, not the tool class.

4. **Spillover test before activation.** Before a new hook goes into the production pipeline: the author writes down at least 3 examples where the hook should NOT fire, and verifies each one passes through.

## Trigger Incident (2026-05-28)

During the refactor-skill phase-2 scans, Opus made several Python subprocess calls (`python3 /tmp/refactor_funclen.py`, `python3 /tmp/refactor_state.py`, etc.) — all as FOREGROUND tool calls (no `run_in_background=true` set). The scripts are pure AST walks, runtime <2s per call.

Several of these calls were auto-rewritten into background execution by the `block_unauthorized_background` hook (or a related one). Symptoms:
- The tool result showed "Command was manually backgrounded by user with ID: ..." even though Opus had not set `run_in_background=true`
- Script output didn't come back directly, but landed in `/private/tmp/.../tasks/<id>.output`
- Python subprocess processes kept sitting in the process table after the Bash tool returned (PIDs 49345, 56850, 56852, 63997, 63999 were manually cleaned up with `kill`)
- Three refactor sub-scans (scripts-in-lib, dev-tooling-gap) could not complete because the output didn't come back in the expected structure

Per user feedback: "hooks produce spillovers this severe this fast, and I can never estimate in advance what processes we'll have in two weeks or whether existing hooks will block them."

## Consequences / TODOs

1. **Audit existing hooks in `src/hooks/`** for over-generality. Which hooks would block 3+ legitimate workflows in the coming weeks?

2. **Concretely to review — `block_unauthorized_background`:** the pattern matching is too broad, catches foreground calls. Either narrow it sharply to "background-marker + non-canonical-sleep" or disable it as a class-wide hook and replace it with use-case-specific ones.

3. **Concretely to review — `block_broad_grep` etc.:** run all `block_*` hooks against the 3-example spillover test.

4. **New hook-design standard in the iterative-dev plugin:** before every new hook, the author MUST document the 3 whitelist examples. CI check optional.

## Cross-Reference

This principle is relevant across plugins (iterative-dev, Monitor_CC `src/hooks`, other project hook collections). Should potentially be materialized as a shared rule in `~/.claude/shared-rules/` once the principle has been independently verified across multiple projects.

## Sources

- Session 2026-05-28: refactor-skill phase-2 spillover observation (see session log)
- User statement: "hooks going forward should be extremely use-case-specific and never general"
- Project hooks: `src/hooks/block_unauthorized_background.py`, `src/hooks/block_broad_grep.py`, further `block_*.py` — see `src/hooks/DOCS.md`
