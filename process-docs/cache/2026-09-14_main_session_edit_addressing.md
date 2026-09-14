# 2026-09-14 — Edit addressing in the main session: the old text is still sent

## Observation

The measurement in this area from 2026-09-13 compared the Edit tool against `sed -i ''` over 20
files, one line replaced per file. Edit came out at 8115 CC over 22 calls, sed at 4245 over 20,
a gap of 157 tokens per call. The stated cause was structural: Edit carries `old_string`
verbatim so it can locate the target, while sed addressed the line by number and carried nothing
but `1s/.*/MARKER/`.

The conclusion drawn from that run was "Bash wins over Edit". In this session that conclusion was
applied to rule-file edits in `~/.claude/shared-rules/main/communication.md`, and it was applied
wrongly. Three edits were made with a `python3 - <<'EOF'` heredoc that searched for the full old
block as a literal string, asserted its presence, and replaced it. Each of those calls carried
roughly 400 to 500 bytes, most of it the old text, verbatim.

The user named the contradiction directly: the Edit tool was rejected for resending the old text,
and the replacement resends it too.

## What the measurement actually showed

The saving sat in the addressing, not in the lane. Bash with a literal old-string search has
Edit's cost profile minus the per-call envelope, which the same run put at about 65 tokens for
the Write-against-heredoc pair. So a literal-search heredoc captures roughly the smaller half of
the 157 and leaves the structural half on the table.

## The trade-off that produced the heredoc

Line-number addressing is the cheapest form and the least safe one. A number is only correct as
long as nothing above it moved, and a wrong number edits the wrong line silently. The heredoc's
`assert old in t` fails loudly instead: it aborts when the anchor is missing and when the
replacement is already present, so a double application is impossible.

That guard is worth something. What was not done is weighing it against the measured cost before
choosing the form.

## The middle path

`sed` can address through a short unique pattern instead of a line number. The uniqueness check
survives, and the transmitted text shrinks from the whole block to a few words. The last edit of
this session used it: replacing the line starting with `- The form is free` sent four words of
anchor rather than the full sentence.

The open question is where the anchor form stops working. A whole-paragraph replacement still
needs the paragraph. A multi-line block with no unique first line still needs more anchor than a
one-liner. Neither boundary is measured.

## Decision taken on 2026-09-14

No rule change. The user's call was to collect data across a few sessions first, rather than
switch the editing form on the strength of one run plus one session's observation.

What a successor should collect: which edit forms actually get used in a main session, how large
the transmitted anchor is per call, and whether an anchored `sed` ever failed to locate its
target. The 2026-09-13 run measured 20 uniform one-line replacements in a corpus built for the
purpose; main-session edits are fewer, larger, and land in prose files, so the per-call numbers
from that run are not assumed to transfer.
