# INFRASTRUCTURE
from test_strip_fix_fixtures import _O, check, real_sr_text, text_block, _strip_system_reminders

# FUNCTIONS

# ── ENV-CONTEXT SR: CC 2.1.258 TRAILING-SENTENCES FIX (2026-09) ──────────────
# CC 2.1.258 appends two sentences after the email address before `# currentDate`. The old
# `_ENV_CONTEXT_RE` required `\n` immediately after `gmail\.com\.`, so `fullmatch` failed and the
# `_PRESERVE_PREAMBLE` guard (same preamble as CLAUDE.md context blocks) kept the whole block,
# reaching the API in message 0 of every session. Fix: `[^\n]*` after the email sentence tolerates
# any trailing text on that one line. Measured over `src/logs/dual_log/*_original.jsonl` (main
# checkout, 2026-09): 1866 occurrences of the May-2026 form, 699 of the 2.1.258 form, both
# top-level and both must strip; 242 occurrences of CC bundling `# claudeMd` content AND
# `# userEmail` into ONE `<system-reminder>` block — must stay preserved (real CLAUDE.md content),
# T44 pins this exact shape.

def t40_env_context_may_2026_form_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com.\n"
        "# currentDate\n"
        "Today's date is 2026-05-30.\n\n"
        "      IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T40_env_context_may_form_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t41_env_context_cc258_form_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# currentDate\n"
        "Today's date is 2026-09-05.\n\n"
        "      IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T41_env_context_cc258_form_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t42_claudemd_context_block_preserved():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# claudeMd\nCodebase and user instructions are shown below. Be sure to adhere to these "
        "instructions. IMPORTANT: These instructions OVERRIDE any default behavior.\n\n"
        "Contents of /Users/x/project/CLAUDE.md (project instructions, checked into the codebase):\n\n"
        "# some-project\n\nProject-specific rules go here, not env-context at all."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T42_claudemd_block_preserved', result[0]['text'] == sr, repr(result[0]['text'])[:120])


def t43_env_context_different_email_preserved():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is someoneelse@example.com.\n"
        "# currentDate\n"
        "Today's date is 2026-09-05.\n\n"
        "      IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T43_env_context_different_email_preserved', result[0]['text'] == sr, repr(result[0]['text'])[:120])


# T44 — real corpus shape (src/logs/dual_log, main checkout, 2026-09, 242 occurrences): CC
# bundles `# claudeMd` project content AND `# userEmail`/`# currentDate` into ONE SR block rather
# than two separate blocks. `_ENV_CONTEXT_RE.fullmatch` correctly fails (the inner text is not
# JUST the env-context block), so the `_PRESERVE_PREAMBLE` guard preserves the whole thing —
# losing the CLAUDE.md content would be worse than the ~250 bytes of unstripped env-context noise.
def t44_bundled_claudemd_and_env_context_preserved():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# claudeMd\nCodebase and user instructions are shown below. Be sure to adhere to these "
        "instructions.\n\nContents of /Users/x/wise2627/CLAUDE.md (project instructions, checked "
        "into the codebase):\n\n# wise2627\n\nSome real project instructions here.\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# currentDate\n"
        "Today's date is 2026-09-04.\n\n"
        "      IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T44_bundled_claudemd_env_context_preserved', result[0]['text'] == sr, repr(result[0]['text'])[:120])


# ── ENV-CONTEXT SR: gitStatus WIDENING (2026-09) ─────────────────────────────
# Current CC build replaced `# currentDate` with a `# gitStatus` section in the same bundled
# env-context block — no `# currentDate` anywhere, still exactly one `IMPORTANT:` footer.
# `_ENV_CONTEXT_RE`'s alternation now accepts EITHER `# currentDate\n...` OR `# gitStatus\n` +
# the stable header sentence + a free body (`.*?`, DOTALL) up to the `IMPORTANT:` footer — the
# body is deliberately NOT anchored field-by-field (no per-line `Current branch:`/`Main branch:`/
# `Git user:`/`Status:`/`Recent commits:` requirement). An initial version of this fix DID
# enumerate those 5 fields with a fixed blank-line structure, generalized from only the 3 corpus
# blocks below — review caught that each enumerated field is a brittle anchor with zero protective
# value (fullmatch is already pinned by the preamble, the literal email, and the IMPORTANT footer;
# a block carrying all three IS the env-context block) and a guaranteed re-break on the next CC
# gitStatus layout change. CC issue reports confirm the layout is not fixed: #86891's snapshot
# has only Current branch / Main branch / Status, no Git user line and no Recent commits section
# (T50); #43250 has no blank lines between fields at all and an inline `Status: clean` (T51) —
# both would have failed the field-enumerated version. T45/T46 are copied verbatim from
# `src/logs/dual_log/*_original.jsonl` (main checkout, 2026-09 measurement, 3 distinct blocks,
# 973-1045 chars each, see process-docs/proxy_noise_strip/ for the fresh count). T47/T48 cover
# dirty `git status --short` lines and a detached `HEAD` branch, neither observed in the current
# corpus window. T49 confirms the bundled `# claudeMd` + gitStatus shape (unobserved in this
# corpus, but structurally identical to T44's bundled currentDate case) is still preserved whole
# by the same `_PRESERVE_PREAMBLE` fallback.

def t45_env_context_gitstatus_corpus_block_main_clean_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: main\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Git user: Bruno Winter\n\n"
        "Status:\n(clean)\n\n"
        "Recent commits:\n"
        "19f939e docs: phase 4 section in main session entry\n"
        "a64d71a merge: worker docs-dev-c\n"
        "de92650 docs: recap for docs-dev-c\n"
        "e8a863e docs: de-backtick missing hook path in bead_tracker DOCS.md\n"
        "bbb26f7 docs: create DOCS.md for 7 dev/ areas (docs-dev-c)\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T45_gitstatus_main_clean_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t46_env_context_gitstatus_corpus_block_integration_branch_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: integration\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Git user: Bruno Winter\n\n"
        "Status:\n(clean)\n\n"
        "Recent commits:\n"
        "b582e71 merge: worker cfg3\n"
        "d7d61ad docs: salvage six DOCS.md files before lean rewrite\n"
        "03603f8 merge: worker cfg3\n"
        "9b6a2a7 merge: worker cfg2\n"
        "49816fc merge: worker cfg1\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T46_gitstatus_integration_branch_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t47_env_context_gitstatus_dirty_status_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: feature/envstrip\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Git user: Bruno Winter\n\n"
        "Status:\n"
        " M src/proxy/strip_sr.py\n"
        "?? dev/proxy/new_file.py\n\n"
        "Recent commits:\n"
        "abc1234 fix: something\n"
        "def5678 feat: other thing\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T47_gitstatus_dirty_status_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t48_env_context_gitstatus_head_branch_stripped():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: HEAD\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Git user: Bruno Winter\n\n"
        "Status:\n(clean)\n\n"
        "Recent commits:\n"
        "19f939e docs: phase 4 section in main session entry\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T48_gitstatus_head_branch_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t49_bundled_claudemd_and_gitstatus_preserved():
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# claudeMd\nCodebase and user instructions are shown below. Be sure to adhere to these "
        "instructions.\n\nContents of /Users/x/wise2627/CLAUDE.md (project instructions, checked "
        "into the codebase):\n\n# wise2627\n\nSome real project instructions here.\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: main\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Git user: Bruno Winter\n\n"
        "Status:\n(clean)\n\n"
        "Recent commits:\n"
        "19f939e docs: phase 4 section in main session entry\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T49_bundled_claudemd_gitstatus_preserved', result[0]['text'] == sr, repr(result[0]['text'])[:120])


def t50_env_context_gitstatus_issue86891_shape_stripped():
    # CC issue #86891 — snapshot has only Current branch / Main branch / Status, no Git user
    # line and no Recent commits section at all.
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n\n"
        "Current branch: main\n\n"
        "Main branch (you will usually use this for PRs): main\n\n"
        "Status:\n(clean)\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T50_gitstatus_issue86891_shape_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])


def t51_env_context_gitstatus_issue43250_shape_stripped():
    # CC issue #43250 — fields have no blank lines between them, Status is inline on one line.
    body = (
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\n"
        "The user's email address is brunowinter7934@gmail.com. Use it only to identify the user, "
        "such as for authorship, attribution, or filtering their own work. Never send it to an "
        "unrelated service, such as in a request header, URL, or payload, unless the user explicitly asks.\n"
        "# gitStatus\n"
        "This is the git status at the start of the conversation. Note that this status is a "
        "snapshot in time, and will not update during the conversation.\n"
        "Current branch: main\n"
        "Main branch (you will usually use this for PRs): main\n"
        "Git user: Bruno Winter\n"
        "Status: clean\n"
        "Recent commits:\n"
        "19f939e docs: something\n\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task."
    )
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T51_gitstatus_issue43250_shape_stripped', _O not in result[0]['text'], repr(result[0]['text'])[:120])
