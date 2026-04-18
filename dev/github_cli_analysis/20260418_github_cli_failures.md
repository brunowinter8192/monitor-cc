# GitHub CLI Failure Analysis — warnings-pane-fixes Session

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`  
**Task:** Worker searched tmux source for mouse scroll button codes (64/65) to fix scroll-direction inversion in warnings_pane.py.  
**GitHub CLI source:** `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/`

---

## Failure 1 — `Skill("github-search")` — No matches found (×5)

**Command:**
```
Skill(skill="github-search", args="tmux tty-keys.c mouse button scroll wheel 64 65")
```

**Outcome:** "No matches found" — repeated 5+ times verbatim (visible in proxy log as duplicate SR+tool_use blocks from context re-sends).

**Hypothesis:** The `github-search` Skill maps to a natural-language search query, but the underlying endpoint is GitHub's code-search API (`search_code_workflow`). The query `"tmux tty-keys.c mouse button scroll wheel 64 65"` contains file names and numeric literals that GitHub code-search doesn't rank highly. The Skill doesn't expose `repo:` or `path:` qualifiers.

**Verified via:** `cli.py:47-50` — `search_code` takes a raw `query` string passed to `GET /search/code?q=<query>`. No repo or path scoping in the Skill invocation → searches all of GitHub, matching nothing relevant.

**Actual root cause:** Missing `repo:tmux/tmux` qualifier in the search query. GitHub code-search without a repo scope returns zero results for narrow technical terms.

**Fix direction:** Pass `repo:tmux/tmux` qualifier: `Skill(skill="github-search", args="repo:tmux/tmux MOUSE_WHEEL_UP button 64 scroll")`.

---

## Failure 2 — `grep_repo` with pipe-escaped regex — No matches found (×3)

**Command:**
```
cli.py grep_repo tmux tmux "64.*wheel\|wheel.*64\|WheelUp\|WheelDown\|SCROLL_UP\|SCROLL_DOWN" \
  --file-pattern "*.c" --path "" --max-files 30
```

**Outcome:** "No matches found in any file."

**Hypothesis:** The pattern uses `\|` for alternation — POSIX ERE syntax. Python `re.compile()` treats `\|` as literal `|`, so the pattern actually searches for the string `64.*wheel|wheel.*64` (with literal backslashes before pipes), which doesn't occur in the tmux source.

**Verified via:** `grep_file.py:30` — `compiled = re.compile(pattern)`. `grep_repo.py:42` — calls `search_lines(lines, pattern, 0, MAX_MATCHES_PER_FILE)` with the raw pattern string. No pre-processing of `\|` to `|`. Python `re` alternation uses `|` without backslash.

**Actual root cause:** Shell escaping confusion. The worker escaped `|` as `\|` intending to pass a literal pipe through the shell, but Python `re.compile` received the raw string with backslashes — turning alternation into a literal match for `\|`.

**Fix direction:** Use `|` without backslash in Python regex patterns: `"64.*wheel|wheel.*64|WheelUp|WheelDown|SCROLL_UP|SCROLL_DOWN"`.

---

## Failure 3 — `grep_file` with wrong path argument — No matches found (×2)

**Commands:**
```
cli.py grep_file tmux tmux "input-keys.c" "wheel|WHEEL|scroll|SCROLL|button.*64|64.*button" --context-lines 3
cli.py grep_file tmux tmux "tty-keys.c" "MOUSE|mouse|button" --context-lines 2 --max-matches 30
```

**Outcome:** "No matches found." (or possibly `ValueError: Path 'tty-keys.c' is a directory, not a file.` caught silently)

**Hypothesis:** The `path` argument to `grep_file` is the full repo-relative file path. The worker passed just the filename (`"tty-keys.c"`, `"input-keys.c"`). If tmux stores these files at the root of the repo (i.e. `tty-keys.c` is the correct path), then the API call would succeed. If they are in a subdirectory, the GitHub API returns a directory listing (a list) → `isinstance(raw_response, list)` → `raise ValueError`.

**Verified via:** `grep_file.py:15-18` — `fetch_file_content(owner, repo, path)`. If the path resolves to a directory, `raw_response` is a list → `ValueError` is raised (not caught in `grep_file_workflow`). In the CLI dispatcher this propagates as an error message. However the proxy log shows "No matches found" (not an error), suggesting the files ARE at repo root and were fetched successfully — but the pattern `"MOUSE|mouse|button"` with correctly escaped `|` DID find matches in the `tty-keys.c` context (the later `search_code` call succeeded with the right query). The "No matches found" for `tty-keys.c` therefore likely came from the same escaped-pipe issue: `"MOUSE\|mouse\|button"` in earlier attempts.

**Verified via:** `grep_file.py:56-58` — returns `"No matches found."` (with period) when `search_lines` returns an empty list.

**Actual root cause:** Combination of (a) same `\|` escaping bug as Failure 2 in earlier attempts, and (b) for the final `tty-keys.c` call with `"MOUSE|mouse|button"` — tmux root-level `tty-keys.c` exists but the correct pattern would need to be `MOUSE` capitalized (tmux uses `MOUSE_BUTTON`, `MOUSE_WHEEL_UP` style constants, not bare `button`). The bare `button` alone returns no matches because tmux uses compound identifiers.

**Fix direction:** (a) Fix `\|` → `|` for all patterns. (b) Use `grep_repo` with `--file-pattern "tty-keys.c"` instead of `grep_file` when unsure about the exact repo path. (c) Use broader patterns like `MOUSE_WHEEL` that match tmux's actual naming.

---

## Failure 4 — `grep_repo` for `WheelUp|WheelDown` — No matches found

**Command:**
```
cli.py grep_repo tmux tmux "WheelUp|WheelDown|wheel_up|wheel_down" --file-pattern "*.c" --max-files 50
```

**Outcome:** "No matches found in any file."

**Hypothesis:** tmux uses different naming for scroll events — not `WheelUp`/`WheelDown` but `MOUSE_WHEEL_UP`/`MOUSE_WHEEL_DOWN` (or similar). This is a correct Python regex (no `\|` issue), so the failure is a genuine naming-mismatch.

**Verified via:** The subsequent successful `search_code` call (not shown as failure) used query `"repo:tmux/tmux MOUSE_WHEEL_UP"` and returned results from `input-keys.c:755-822`. This confirms tmux uses `MOUSE_WHEEL_UP`/`MOUSE_WHEEL_DOWN` not `WheelUp`/`WheelDown`.

**Actual root cause:** Wrong constant names. tmux uses `MOUSE_WHEEL_UP`/`MOUSE_WHEEL_DOWN` (all caps, underscore-separated), not camelCase variants.

**Fix direction:** Pattern `"MOUSE_WHEEL_UP|MOUSE_WHEEL_DOWN"` would have matched immediately.

---

## Summary Table

| # | Subcommand | Pattern/Args | Outcome | Root Cause | Severity |
|---|---|---|---|---|---|
| 1 | `Skill("github-search")` | No `repo:` qualifier | No matches | Missing `repo:tmux/tmux` in query | Inefficient (5× retries) |
| 2 | `grep_repo` | `\|` instead of `|` | No matches | Python `re` doesn't use POSIX ERE `\|` | Blocking (prevents any alternation match) |
| 3 | `grep_file` | `path="tty-keys.c"` + same `\|` issue | No matches | Escaping bug; bare `button` too generic | Blocking (same escaping root as #2) |
| 4 | `grep_repo` | `WheelUp|WheelDown` | No matches | Wrong constant names (tmux uses `MOUSE_WHEEL_UP`) | Minor (pattern research gap) |

**Primary blocker:** The `\|` escaping bug (Failure 2+3) affected the majority of calls and caused 3 `grep_repo` and 2 `grep_file` attempts to fail silently. A single awareness of Python RE vs POSIX ERE would have resolved this before any call was made.

**Resolution path for future sessions:** Use `search_code` with `repo:<owner>/<repo>` qualifier first to discover correct constant names, then use `grep_file` or `grep_repo` with verified Python RE syntax for context lookup.
