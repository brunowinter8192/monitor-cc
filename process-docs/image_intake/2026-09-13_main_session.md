# Reading images in a session without the Read tool (2026-09-13, main session)

## Why this came up

The user pasted a screenshot of the proxy pane to show an unstripped `<system-reminder>` block.
The Read tool is blocked in this project (2026-09, Read/Edit/Write blocklist), so the usual path
to an image was closed, and the question became how a main session can see a PNG at all.

## What works today: OCR

`tesseract` is installed (`/opt/homebrew/bin/tesseract`). `tesseract <file.png> - -l deu+eng`
prints the recognized text to stdout, which is an ordinary Bash result. On the screenshot in
question it recovered the full `<system-reminder>` block including `# userEmail` and `# gitStatus`,
enough to identify the defect and start the task. Terminal and UI screenshots are text, so OCR
covers them.

Its limit is equally clear: OCR returns text, never pixels. Layout, diagrams, colored regions and
anything whose meaning is not in its letters do not survive.

## What does NOT work: base64 in a tool result

`base64 -i file.png` is available, but the output is text inside a Bash tool result. A model reads
an image only from a real content block of `type: "image"` with a `source.media_type` and its
base64 data. A base64 string sitting in tool-result text is just tokens - expensive and unreadable.
This was checked before proposing anything, precisely because "just base64 it" is the obvious wrong
answer.

## The open path: proxy-side image injection

This repo's proxy already rewrites request payloads on the wire (`src/proxy/rules.py` and the
inject/strip pass family). An injection that recognizes a marker in a Bash tool result and replaces
it with a real `image` content block would give a main session genuine vision without the Read tool.
Nothing of that exists today: a grep for `image` across `src/proxy/` finds exactly one hit, a block
type listed in `strip_sr.py`'s traversal. So the mechanism is plausible on this codebase, but
entirely unbuilt.

Cost and risk were not measured. Whether the API accepts an injected image block in a position CC
never produced itself is unverified, and so is the effect on the prompt cache, which the injection
would invalidate from the injection point onward.

## Decision taken on 2026-09-13

OCR was used for the session's actual work and was sufficient for it. The injection path was parked
rather than built, because the session's subject was elsewhere and no measurement backed the larger
change.
