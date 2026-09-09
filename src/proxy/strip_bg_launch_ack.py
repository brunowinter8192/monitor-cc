import re

from .payload_helpers import _walk_replace_marker_blocks

# INFRASTRUCTURE

# Fast-path markers — cheap contains check before block walk. Two CC wordings measured
# (dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md, 2026-07-29): wording 1 fires on
# initial background launch, wording 2 fires when the USER manually backgrounds an already-
# running Bash call. Each marker stays narrow/specific to its own wording (not widened to a
# shared broad substring like "with ID:") to preserve the same low-false-positive precision as
# before — a broad marker would reopen the FP-nuke class of bug these markers exist to avoid.
_BG_LAUNCH_ACK_MARKER = 'running in background with ID'
_BG_LAUNCH_ACK_MARKER_2 = 'backgrounded by user with ID'
# Anchored ack prefixes: a genuine CC bg-launch ack ALWAYS starts with one of these exact
# prefixes. The strip decision uses startswith() on the lstripped text (NOT substring-anywhere),
# so a large tool_result or user message that merely CONTAINS either phrase as data is never
# destroyed (was the FP-nuke bug).
_BG_LAUNCH_ACK_PREFIX = 'Command running in background with ID:'
_BG_LAUNCH_ACK_PREFIX_2 = 'Command was manually backgrounded by user with ID:'

_BG_LAUNCH_ACK_MSG = (
    'Command is running in the background. Do NOT check, poll, or read its output — '
    'just wait until it finishes (you will get a completion notice).'
)

# Main (orchestrator) context version — sharper than the shared wording above: explicitly names
# going idle and ties the wait to THIS exact task id, since main is the context that arms the
# orchestrator's wake-up command (worker-cli wait) — a stacked/duplicate arm is a main-context-only
# failure mode (workers don't arm the orchestrator's own wake-up).
_BG_LAUNCH_ACK_MSG_MAIN = (
    'Command is running in the background. Do NOT check, poll, or read its output, and do NOT '
    'arm another background timer — go idle now and wait; you will get a completion notice for '
    'this exact task ID when it finishes.'
)

# Recover id/path FROM the ack text being replaced — shared by both wordings. Real recorded
# shapes (dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md, 2026-07-29):
#   wording 1: "Command running in background with ID: <id>. Output is being written to: <path>.
#              You will be notified when it completes. To check interim output, use Read on that
#              file path."
#   wording 2: "Command was manually backgrounded by user with ID: <id>. Output is being written
#              to: <path>" — no trailing sentence; measured occurrences end right after the path.
# ID: anchored on the "with ID:" fragment common to both wordings, not the wording-specific full
# sentence — safe because this regex only ever runs on text _is_bg_launch_ack has ALREADY
# confirmed is a genuine, block-initial-anchored ack (every call site gates on it first); the FP
# guard lives in that anchor, not here. Id group excludes '.' (ids are alnum tokens in every
# measured occurrence, both wordings).
# PATH: non-greedy up to whichever comes first — the wording-1 terminator (". You will be
# notified"), a literal newline, or end-of-string. The newline/end-of-string branches exist for
# wording 2, whose ack can BE the complete block (nothing follows) but is not guaranteed to be —
# without a newline bound, trailing content sharing the same block (measured: possible per the
# blast-radius classification of this pass — "ANY trailing content after the ack in that block is
# also discarded" by the replacement) would be swallowed into the path capture. DOTALL is kept
# (needed by the wording-1 branch: an internal dot in the path, e.g. the ".output" extension,
# doesn't truncate it early) — the explicit "|\n|" alternative bounds ONLY the no-sentence
# fallback, it does not change wording-1 matching (that branch is tried first in the alternation
# and always wins before any embedded newline is reached, since no measured wording-1 path
# contains one).
_ACK_ID_RE = re.compile(r'with ID:\s*([^.]*)\.')
_ACK_PATH_RE = re.compile(
    r'Output is being written to:\s*(.*?)(?:\.\s*You will be notified|\n|\s*$)', re.DOTALL
)


# True only for a genuine bg-launch ack: either known wording's prefix, anchored at the start of
# the text.
def _is_bg_launch_ack(text):
    stripped = text.lstrip()
    return stripped.startswith(_BG_LAUNCH_ACK_PREFIX) or stripped.startswith(_BG_LAUNCH_ACK_PREFIX_2)


# ORCHESTRATOR

# Replace entire content of any block whose text STARTS WITH either bg-launch-ack prefix with the
# same 3-line hold message (msg + optional Output: + optional ID:, recovered from the ack itself)
# — both wordings produce identical output shape. Anchored (not substring-anywhere): legitimate
# content that merely contains either phrase is kept.
# Covers all 4 content shapes: str, list[text], list[tool_result+str], list[tool_result+list] —
# via the shared payload_helpers._walk_replace_marker_blocks walk (folded 2026-09, byte-identical
# shape to strip_interrupt_marker.py's own walk, verified before folding).
# is_main selects the replacement wording (_BG_LAUNCH_ACK_MSG_MAIN vs the shared default) —
# False preserves the exact wording every existing caller already expects.
# Returns (new_content, removed_chunks) — removed_chunks: original texts of replaced blocks.
def _strip_bg_launch_ack(content, is_main=False):
    return _walk_replace_marker_blocks(
        content, _is_bg_launch_ack, lambda text: _build_launch_ack_replacement(text, is_main)
    )


# FUNCTIONS

# Build the 3-line hold message from a genuine ack's text: msg, then Output: <path> (if the ack's
# path was recovered), then ID: <id> (if the ack's id was recovered). A value that fails to extract
# is OMITTED — never "ID: None", never a dangling "ID:" with nothing after it. Not observed in real
# data (id+path present in every measured ack), defensive only.
def _build_launch_ack_replacement(ack_text, is_main=False):
    id_match = _ACK_ID_RE.search(ack_text)
    path_match = _ACK_PATH_RE.search(ack_text)
    task_id = id_match.group(1).strip() if id_match else ''
    path = path_match.group(1).strip() if path_match else ''
    lines = [_BG_LAUNCH_ACK_MSG_MAIN if is_main else _BG_LAUNCH_ACK_MSG]
    if path:
        lines.append('Output: ' + path)
    if task_id:
        lines.append('ID: ' + task_id)
    return '\n'.join(lines) + '\n'
