"""Token classification rules for sleep-pattern analysis."""

# INFRASTRUCTURE

_TRIVIAL = {
    "echo", "ls", "cat", "pwd", "grep", "wc", "head", "tail", "git",
    "rm", "mkdir", "cp", "mv", "date", "printf", "true", "false", "test", "gc",
}

# Mixed tokens: safe for some subcommands, load-bearing for others
_MIXED_NOTES = {
    "rag-cli":    "MIXED — `rag-cli server restart/start` is async (server spawn); "
                  "read-only subcommands (search, list) are sync.",
    "bd":         "MIXED — `bd dolt start` spawns the Dolt server (async); "
                  "label/comment/list ops are sync.",
    "worker-cli": "MIXED — `worker-cli kill/spawn` are async; status/list are sync.",
}

_LOADBEAR = {"kill", "pkill", "killall", "launchctl", "systemctl", "tmux", "nohup"}

_TRIVIAL_REASONS = {
    "echo":  "prints to stdout and returns; no process spawned, no state mutation",
    "true":  "exits 0 immediately; appears as `|| true; sleep N` — the `true` is a "
             "swallowed-error guard, not async work",
    "git":   "git commands (status, push, commit) complete synchronously; push may "
             "take seconds but finishes before returning",
    "ls": "synchronous directory listing", "cat": "synchronous file read",
    "pwd": "synchronous", "grep": "synchronous pattern search",
    "wc": "synchronous", "head": "synchronous", "tail": "synchronous",
    "rm": "synchronous file removal", "mkdir": "synchronous",
    "cp": "synchronous", "mv": "synchronous", "gc": "git commit wrapper, synchronous",
}

_LOAD_REASONS = {
    "kill":      "sends signal to process; OS scheduler needs time to deliver SIGKILL and "
                 "reap the child — polling immediately after kill will see the process still alive",
    "pkill":     "same as kill; pattern-based, may target multiple processes",
    "killall":   "same",
    "launchctl": "kickstart/bootout are async — the service reaches 'running' state "
                 "asynchronously; pgrep checks after sleep verify the daemon is up",
    "systemctl": "service start/stop is async by default",
    "tmux":      "some tmux commands mutate session state asynchronously (pipe-pane, "
                 "new-session, send-keys); sleep ensures the operation has propagated",
    "nohup":     "spawns a background process; sleep gives it time to initialize",
}


# FUNCTIONS


# Append trivial/load-bearing/mixed/unclassifiable classification tables
def add_classification(lines: list, before_counts: dict) -> None:
    trivial, loadbear, unclear = [], [], []
    for tok, recs in sorted(before_counts.items(), key=lambda x: -len(x[1])):
        bucket = (trivial if tok in _TRIVIAL else
                  loadbear if tok in _LOADBEAR else unclear)
        bucket.append((tok, recs))

    lines += [
        "### Candidate trivial-sync tokens (safe to strip)", "",
        "Each token below returns synchronously on completion: no background process is "
        "spawned and no externally-visible state needs settling time before the next command "
        "can safely proceed. A rewrite hook can strip `sleep N` following these tokens "
        "without risk.", "",
    ]
    for tok, recs in trivial:
        snip   = recs[0]["cmd_snippet"][:120].replace("|", "\\|")
        reason = _TRIVIAL_REASONS.get(tok, "synchronous, no async side-effect")
        lines.append(f"- **`{tok}`** ({len(recs)}) — {reason}. Example: `{snip}`")

    lines += ["", "### Clearly load-bearing tokens", "",
              "Sleep after these tokens is doing real work. Do not strip.", ""]
    for tok, recs in loadbear:
        snip   = recs[0]["cmd_snippet"][:120].replace("|", "\\|")
        reason = _LOAD_REASONS.get(tok, "async state change")
        lines.append(f"- **`{tok}`** ({len(recs)}) — {reason}. Example: `{snip}`")

    lines += ["", "### Mixed tokens (require per-subcommand inspection)", ""]
    for tok, note in _MIXED_NOTES.items():
        if tok in before_counts:
            recs = before_counts[tok]
            snip = recs[0]["cmd_snippet"][:120].replace("|", "\\|")
            lines.append(f"- **`{tok}`** ({len(recs)}) — {note} Example: `{snip}`")

    lines += ["", "### Unclassifiable tail", "",
              "| Token | Count | Example |", "|---|---|---|"]
    skip = _TRIVIAL | _LOADBEAR | set(_MIXED_NOTES)
    for tok, recs in sorted(unclear, key=lambda x: -len(x[1])):
        if tok in skip:
            continue
        snip = recs[0]["cmd_snippet"][:80].replace("|", "\\|")
        lines.append(f"| `{tok}` | {len(recs)} | `{snip}` |")
