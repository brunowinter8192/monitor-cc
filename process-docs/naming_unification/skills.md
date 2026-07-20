# Naming Unification — Skills

Part of Bead uoyx. Hard rule (user 2026-06-02): **plugins contain ONLY skills** — no commands, no agents, no MCP servers.

## Skill naming convention (DECISION, user-confirmed 2026-06-02)

Every skill name = `<plugin-name>-<descriptor>`. Plugin-name prefix → instant attribution. Redundant tool-name in the descriptor is dropped (`gh-cli-search`, NOT `gh-cli-github-search`).

Three places MUST be identical per skill (else drift-error, see tooling.md § drift validation):
- folder name `skills/<name>/`
- SKILL.md frontmatter `name:`
- registration in `plugin.json` `"skills"`

## Skill map (current → target)

| Plugin (neu) | Skill folder heute | SKILL.md name heute | → Ziel-Name (alle 3 Stellen) |
|---|---|---|---|
| `gh-cli` | `github-search` | `github-search` | `gh-cli-search` |
| `reddit-cli` | `reddit-search` | `reddit-search` | `reddit-cli-search` |
| `searxng-cli` | `web-research` | `web-research` | `searxng-cli-web-research` |
| `searxng-cli` | `capture-and-index` | `capture-and-index` | `searxng-cli-capture-and-index` |
| `iterative-dev` | `refactor` | `refactor` | `iterative-dev-refactor` |

5 skills over 4 plugins. `rag-cli` has **NO skill** — usage already in shared-rules + covered by the `rag-cli` wrapper.

## Deletions (same batch)

- `iterative-dev`: DELETE agent `agents/code-investigate-specialist.md` + remove `"agents"` key from plugin.json.
- `iterative-dev`: DELETE skill `rule-consolidation` (folder + registration). Remove its reference in shared-rules (end-of-day rule-merging).
- `iterative-dev`, `rag`: remove empty `commands/` folders.
- `searxng`: remove empty `"commands": []` field from plugin.json.
- `rag`: remove `.DS_Store` leftovers in `skills/` and `commands/`.

## searxng registration defect (fix in batch)

plugin.json registers `./skills/cleanup-and-index/` — that folder does NOT exist. Real folder + frontmatter name = `capture-and-index`. Target unifies all three to `searxng-cli-capture-and-index` (rename folder, update SKILL.md `name:`, fix registration). Violates both invariants today (registered-without-source + source-without-registration).

## Downstream reference impact

Skill renames touch external references, not only the plugin repo:
- `github-search` skill is activated by name in shared-rules (`github-search` skill gate). Rename → update rule references.
- `rule-consolidation` deletion → remove its activation reference in shared-rules.
- Any worker-prompt / rule that names a skill by its old name.
Folds into the migration's "hardcoded paths nachziehen" step.
