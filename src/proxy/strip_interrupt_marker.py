# INFRASTRUCTURE
from .payload_helpers import _walk_replace_marker_blocks

# tmux-Escape interruption marker CC records when the proxy sends an Escape keystroke into a
# worker's pane mid-tool-call (bg_escape.py) — CC logs this identically to a genuine user
# Ctrl-C/Escape interrupt, though no user pressed anything. Re-measured (dual-log corpus scan,
# 2026-07-31, deduped to the last/fullest line per src/logs/dual_log/*_original.jsonl session
# file — a raw per-line scan overcounts ~150x because each request log re-embeds the full, growing
# message history of the session): 11 occurrences across 5 session files, ALL role='user', block
# type='text', EVERY occurrence carries a trailing '\n'. Two wordings: 10x
# '[Request interrupted by user]\n', 1x '[Request interrupted by user for tool use]\n'. Block
# position varies (index 1 of 3, 1 of 5, or 0 of 2 — not fixed) — never embedded inside longer
# text in any measured occurrence. The 2026-07-30 header's "1791 occurrences" figure was an
# uncorrected per-request-log count and never reproduced; treat it as wrong.
_INTERRUPT_MARKERS = frozenset({
    '[Request interrupted by user]',
    '[Request interrupted by user for tool use]',
})


# True for a whole-block match against either wording, ignoring only surrounding whitespace (the
# trailing '\n' every real occurrence carries) — NOT substring-anywhere: a genuine user
# paste/transcript that happens to CONTAIN one of these phrases inside longer text (measured in
# the same corpus, e.g. a 180-char user message asking about the marker) must never be nuked (the
# FP-nuke class every other strip_*.py anchors against).
def _is_interrupt_marker(text):
    return text.strip() in _INTERRUPT_MARKERS


# ORCHESTRATOR

# Replace the text of any block that IS the interrupt marker with '.'. The marker occupies its
# own block among others (measured shape: tool_result / marker / injected-wakeup) — content is
# emptied in place rather than spliced out of the list: keeps block count/indices stable for
# downstream index-keyed diffing (rule_ops._ops_from_content_change walks old/new content by
# index), and matches the emptied-block convention ('.') the other strip_*.py passes use for a
# block reduced to nothing (the API rejects an empty text block).
# Covers all 4 content shapes: str, list[text], list[tool_result+str], list[tool_result+list] —
# via the shared payload_helpers._walk_replace_marker_blocks walk (folded 2026-09, byte-identical
# shape to strip_bg_launch_ack.py's own walk, verified before folding).
# Returns (new_content, removed_chunks) — removed_chunks: original marker text per match.
def _strip_interrupt_marker(content):
    return _walk_replace_marker_blocks(content, _is_interrupt_marker, lambda _text: '.')
