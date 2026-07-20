# Beads → GitHub Issues Migration — Plan

Decision 2026-06-02: replace beads/dolt entirely with GitHub Issues across all projects, then decommission beads. Sequenced AFTER the naming-unification structure migration — runs in a FRESH session.

## Why

dolt does not reliably persist the working-set; multiple `bd` mutations in one shell invocation silently lose one (#4135, live on bd 1.0.4); fragile high-maintenance stack (per-project dolt sql-servers, ephemeral ports, auto-import/export churn, custom hooks, opaque IDs).

## Steps (fresh session, post-naming)

1. **Map open beads per project** (all 8). Opus presents the open beads; user picks which to KEEP.
2. **Migrate kept beads → GitHub Issues** in each project's remote: preserve title, body, status (open/closed), labels. Closed/dropped beads NOT migrated.
3. **Delete `~/.claude/shared-rules/opus/beads.md`.** Its content (issue-creation meta-rules + format) is rewritten with gh-issue formalities and kept in the **opus scope** — NOT global (workers must NOT inherit it). The meta-rules (when/how to create an issue, format, source-inventory) stay; only the mechanics change `bd` → `gh`. The gh CLI command reference goes into the gh-cli usage context, opus scope.
4. **Remove everything bead-related from the machine**, EXCEPT the historical write-ups about beads: dolt sql-servers, per-project `.beads/`, the `bd` CLI, bd hooks, bd references in workflow/rules.

## Per-project export volume (migration sizing)

Monitor_CC 256, Reddit 124, searxng 89, RAG 89, blank 38, github 34, Trading 15. (Counts are total export incl. closed; only user-kept open beads migrate.)

## Scope boundary

NOT part of the naming-structure session. The naming session must complete first (new repo names = correct gh-issue targets). beads (bd) stays operational during the naming session.
