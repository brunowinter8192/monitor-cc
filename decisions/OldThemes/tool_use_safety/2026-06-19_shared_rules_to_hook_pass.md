# shared-rules → Hook Migration Pass (2026-06-19)

## Context

Session-Arbeit lag in `~/.claude/shared-rules/` (Leanness-Überarbeitung der opus/worker Rules). Teil davon: die fein-granularen Tool-Mechanik-Regeln in `opus/` gegen das bestehende Hook-System geprüft. Prämisse (vom User): fein-granulare „nutze Tool X nie so"-Regeln kosten JEDE Session Kontext; Hooks feuern nur bei Fehlverhalten und sind daher der Komplettersatz für solche Regeln. Meta-Regeln (Worker-Flow, Phasen, Dispatch/Review/Recap/Successor) bleiben — die kann kein Hook abbilden.

Knüpft an das Damage-Prinzip von `2026-05-22_hook_principle_block_vs_allow.md` an: Hooks blocken nur bei **Schaden** (irreversible Aktion ODER Context-Flood). Friction/Sanity ohne Schaden → durchlassen.

## Block-vs-Rewrite Verfeinerung (output-vs-sanity)

Während der Session als Hebel herausgearbeitet, deckt sich mit dem Damage-Prinzip:

- **Output, mit dem der Agent weiterdenkt** (grep/gh-cli/rag/reads) → MUSS **blocken**. Ein stiller Rewrite produziert Output der nicht zum Call passt → Agent schließt „hier ist was kaputt" und debuggt in die falsche Richtung. Das ist Schaden (Reasoning-Korruption).
- **Reine Sanity** (Sleeps, fore/background) → Block-vs-Rewrite egal; der Agent konsumiert das Ergebnis nicht. Stiller Rewrite ist frictionsfrei.
- **Cut-Kriterium ist unabhängig davon:** eine Regel ist cutbar wenn ein Hook (existierend ODER zu bauen) den kritischen Fall deckt — nicht „weil der Hook lehrt".

## Was aus shared-rules/opus gecuttet wurde (gegen EXISTIERENDE Hooks)

| Gecuttet | Deckung |
|---|---|
| `workers-1` Timer-Form-Hook-Erklärung (Form blieb) | `block_unauthorized_background` (silent rewrite bg→fg) |
| `workers-2` Post-Spawn-„kein Thinking" + proxy-Backup-Notiz | proxy-side `thinking`-Override |
| `workers-2` „max ONE background task" | ersatzlos (User-Direktive: Sanity, raus) |
| `workers-2` „no manual cat on timer files" | ersatzlos / Teil des Sleep-Antipatterns (Hook 3) |
| `workers-1` „NEVER Opus" | `block_worker_spawn_opus` (Block + Lehr-Message) |

`workers-2` Capture-sed-Filter (98): erst gecuttet → restored → final RAUS. Capture IST im Successor-Flow load-bearing (Opus liest das Pane des sterbenden Workers), ABER der eigentliche Fix ist **Hook 4 (capture-noise rewrite, Issue #25)**: `worker-cli capture` nativ clean wie `response` liefern (Trailer raus, Inhalt bleibt — kein Block, Capture ist Output mit dem Opus weiterdenkt). Bis der Hook steht verlässt man sich darauf dass Opus capture korrekt anwendet; ein paar Token Noise pro Capture sind verkraftbar. Rule raus, Hook ist SOLL.

## Was als Regel bleibt (und warum)

- **Timer-Form `sleep N && echo done`** — bleibt Regel, nicht weil Rewrite nicht lehrt, sondern weil der Worker-Sleep in ~95% aller Sessions gebraucht wird. Hooks sind für das was alle paar Sessions mal anfällt; ein 95%-Pattern darf eine Regel sein.
- **Kill-Disziplin-Meta** (wann killen / wann NICHT — mid-work, Blocker, low-context) — Judgment, bleibt. Nur das *Wie* (raw tmux-chains, pre-kill-status) ging raus → Hooks.

## Zu bauende Hooks (Issue #25, brunowinter8192/monitor-cc)

Die Kill-Disziplin-Regeln (`workers-3:60/62/44`, `tool-use:33`) wurden gecuttet auf Basis dieser noch zu bauenden Hooks:

1. **`block_manual_worker_cleanup`** — block raw `tmux kill-session worker-*` / `git worktree remove .claude/worktrees/...` / `git branch -D <worker-branch>` → „nutze worker-cli kill". Damage-Klasse: irreversibel (Partial-State). Tight: nur `worker-*` / `.claude/worktrees/`.
2. **kill-while-working-Guard** — `worker-cli kill <name>` abfangen, bei status `working` blocken, **fail-OPEN** bei unbekanntem Status. BLOCKIERT durch Status-Bug (s.u.).
3. **Sleep-Strip-Allowlist** — `rewrite_chained_sleep` Allowlist (aktuell nur `echo`/`true`) um read-only-fast cmds erweitern (grep/cat/ls/wc/head/tail/find, git status|log|diff|show, rag-cli search, worker-cli status|list|response) → angehängtes `sleep` strippen.
4. **capture-noise** — `worker-cli capture` Output clean wie `response` (Successor-Flow).

**Status-Bug (Blocker für Hook 2):** `worker-cli status` zeigt einen Worker als `working` an, NACHDEM er am Context-Limit gestorben ist (false `working`). Ein fail-closed Kill-Guard würde daran ersticken → Hook 2 fail-open ODER Status-Detektion fixen.

## FP-Warnung (aus bestehender Evidenz)

`2026-05-22_hook_principle_block_vs_allow.md` belegt: `block_chained_sleep` war mit **45% FP** der größte Fehlalarm-Generator (legitime `launchctl … ; cmd` und `rag-cli … && sleep ; cmd` Chains). Direkte Konsequenz für **Hook 3**: nicht blocken, nur strippen; Allowlist eng halten; und NIE einen legitimen Wait strippen (`start-server ; sleep 2 ; curl` — async gestartet → Sleep bleibt). Nur strippen wenn das vorige Kommando provably read-only-fast ist und nichts Asynchrones gestartet wurde.

## Global-Pass (gleiche Session)

`global/tool-use.md` ebenfalls durchgezogen — Befund: ALLE hookbaren Hard Rules sind schon von EXISTIERENDEN Hooks gedeckt (global war die Quelle, aus der diese Hooks gebaut wurden). **Keine neuen Hooks.** Gecuttet (gegen verifizierten Source):

| Gecuttet | Deckender Hook |
|---|---|
| §3 Grep-Scope (ganze Sektion) | `block_broad_grep` |
| §13 Pfad-Typo (.claire / ..letter) | `block_path_typo` (silent rewrite) |
| §14 Background-Bash deliberate | `block_unauthorized_background` |
| §16 cd-Drift | `block_cd_drift` |
| §4 venv-no-redirect-Zeile | `block_venv_no_redirect` |
| Read „Directories" | `block_read_directory` |
| Read „256KB limit" | `block_read_oversize` |
| Edit „Noop edit" | `block_noop_edit` |
| Git-Safety: amend/force-push/skip-hooks/empty/config | `block_git_destructive` |

`global/tool-use.md`: −176 Zeilen. Behalten: Judgment/Workflow (§1 heredoc, §5 stop-after-2, §6 one-bash-block [parallel-Block via Hook unmöglich, s. `2026-05-30_parallel_tooluse_block_impossible.md`], §7/§8/§9/§11/§15, Soft Rules, Tool-Reference) — kein Hook fängt die. `global/documentation.md` unangetastet (reine Doc-Konvention). Read 25k-token-Zeile blieb (Hook checkt nur Bytes/256KB, nicht Tokens).

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-22_hook_principle_block_vs_allow.md` (Damage-Prinzip + FP-Evidenz)
- `decisions/OldThemes/tool_use_safety/2026-05-22_hook_api_auto_rewrite_works.md` (silent rewrite via updatedInput funktioniert)
- `src/hooks/` (block_unauthorized_background, block_dangerous_kill, block_worker_spawn_opus, rewrite_chained_sleep als Pattern-Referenz)
- Issue brunowinter8192/monitor-cc#25
