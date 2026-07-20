# block_broad_find — $HOME subpath gap discovery

**Session:** broad-find worktree, post-implementation review before merge.

## What we did

Built `block_broad_find.py` modelled on `block_broad_grep.py`. Initial `_resolve_root` handled bare `$HOME`/`${HOME}` tokens by returning `_HOME` directly via an equality check, then called `os.path.expanduser` for all other tokens.

## What we found

The equality check only covered bare tokens. `$HOME/.claude` reached `os.path.expanduser("$HOME/.claude")` which returns the string unchanged (expanduser only recognises `~`-prefix, not `$HOME`). Result: `normpath("$HOME/.claude") = "$HOME/.claude"` ≠ `_CLAUDE` — the broad-root check returned False and the call passed through unblocked.

`find $HOME/.claude -type d` was indistinguishable from `find ~/.claude -type d` in terms of damage class but the hook treated them differently.

## Decision

Replace `$HOME`/`${HOME}` prefix with `~` BEFORE calling `expanduser`, not after:

```python
if token.startswith('${HOME}'):
    token = '~' + token[7:]
elif token.startswith('$HOME'):
    token = '~' + token[5:]
return os.path.normpath(os.path.expanduser(token))
```

Rationale for prefix-swap over other options:
- `os.path.expandvars` would expand ALL env vars (over-broad, `$SOME_VAR/path` could match unexpectedly)
- Explicit `os.environ.get('HOME')` string replacement: same effect but more fragile (doesn't handle `${HOME}` cleanly in one pass)
- Prefix-swap to `~` is minimal, targeted, and lets `expanduser` handle all subpath forms uniformly — `$HOME/.claude/worktrees/x` → `~/.claude/worktrees/x` → correctly resolved

## Fix confirmed

Smoke case added: `find $HOME/.claude -type d` → exit 2 (BLOCK). 18 → 19 cases, all green.
`$HOME/anything` and `${HOME}/anything` forms now all resolve through the same path as their `~/` equivalents.
