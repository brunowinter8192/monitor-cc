# Naming Unification — Plugin Tooling

Part of Bead uoyx.

## plugin-publish (current behavior)

Script: `~/Documents/ai/Meta/blank/bin/plugin-publish` (symlink `~/.local/bin/plugin-publish`). Edit-and-deploy for an ALREADY-INSTALLED plugin. Steps: locate source repo (upward search for `.claude-plugin/plugin.json`) → refuse if working tree dirty → `git push` → compare plugin.json version vs `installed_plugins.json` → mkdir cache dir on version bump → rsync source→cache (honors .gitignore, preserves venv/.env) → atomic update of `installed_plugins.json` (installPath/version/sha/lastUpdated, backup to /tmp) → kill MCP server process → restart hint. **Keyed by `<plugin-name>@brunowinter-plugins`.** Flags: `--dry-run`, `--no-push`, `--no-restart`.

## Rename gap (KNOWN — handle manually in migration)

plugin-publish keys on plugin NAME → it cannot perform a rename. Renaming `github-research`→`gh-cli`: the script looks up `gh-cli@brunowinter-plugins` in installed_plugins.json, doesn't find it, aborts with "Run '/plugin install' first". Old installed entry + old cache dir are left orphaned.

Per-plugin rename sequence (manual):
1. Rename source dir + remote repo + plugin.json `name` + skill folders/names + SKILL.md `name:`.
2. Update marketplace.json (claude-plugins repo) with new plugin name + new repo.
3. `claude plugin uninstall <old>@brunowinter-plugins -s user -y`
4. `claude plugin install <new>@brunowinter-plugins -s user`
5. `plugin-publish` from renamed source (key now matches) → syncs cache + installed_plugins.json.
6. Remove orphaned old cache dirs.
7. CC restart.

## MCP-kill step now DEAD CODE

No plugin has an MCP server anymore (user 2026-06-02 — final marketplace set is 5 skill-only plugins). plugin-publish step "kill `<name>.*server.py`" matches nothing. Candidate for removal during the tooling pass.

## PROPOSED enhancement — manifest ↔ source drift validation

plugin-publish should FAIL **before** sync on skill-registration drift. Bidirectional check between plugin.json `"skills"` and on-disk skills (folder + SKILL.md `name:`). Match key = the skill NAME; it must be identical across folder name, frontmatter `name:`, and manifest registration.

- ERROR-A: skill present in source (folder/SKILL.md) but NOT registered in manifest.
- ERROR-B: skill registered in manifest but NO matching source (folder/frontmatter name absent).

User example: manifest `iterative-dev-refactor` vs frontmatter `refactor` → **two** errors — B (`iterative-dev-refactor` registered, not in source) AND A (`refactor` in source, not in manifest). The two-error outcome is the expected, correct behavior.

Status: PROPOSED, not implemented. Implementation is a cross-project edit in iterative-dev source (`Meta/blank/bin/plugin-publish`), part of the migration batch.

## situational/plugins.md — STALE, rewrite-or-delete target

`~/.claude/shared-rules/situational/plugins.md`: the Plugin Catalog + Agent-vs-Skill sections describe agents, commands, MCP servers, and skills that no longer exist on disk (e.g. iterative-dev listed with "eval-agent Skill, git-committer Agent, eval-spawn Command"; github-research with "github-search Agent, MCP Server"). Old plugin names + old paths throughout. Either delete or rewrite to current state (5 skill-only plugins, no MCP, new `-cli` names) in the migration batch.
