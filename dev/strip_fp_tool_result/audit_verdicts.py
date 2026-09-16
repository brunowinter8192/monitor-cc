# INFRASTRUCTURE

_MC = 'api_requests_opus_monitor_cc_1785259250_original.jsonl'
_PO = 'api_requests_opus_posts_1785266871_original.jsonl'
_W2 = 'api_requests_opus_wise2627_1785240377_original.jsonl'
_CR = 'api_requests_worker_85d6f25b_capture-monitor-cc-ref_1785272207_original.jsonl'
_MANUAL_VERDICTS = {
    (_MC, 22, 0, 12):   ('genuine CC injection', "Bash ran `ls .../websearch; grep ... download_pdf ...` — real command tripped block_broad_grep.py; prefix is the whole tool_result (context_before empty), advisory text follows immediately."),
    (_MC, 53, 0, 27):   ('genuine CC injection', "Bash `sleep 600 && echo done` with run_in_background=true — genuine CC bg-launch ack; context_before='Command ', context_after='.' (the entire tool_result)."),
    (_MC, 66, 0, 33):   ('genuine CC injection', "Same pattern as msg[53]: real backgrounded `sleep 600` — genuine ack."),
    (_MC, 77, 0, 38):   ('genuine CC injection', "Bash ran `cd .../worktrees/pdf-refs && grep ...` — real command tripped block_cd_drift.py (cd into worktree); prefix is the whole tool_result."),
    (_MC, 83, 0, 41):   ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 120, 0, 58):  ('genuine CC injection', "Bash ran a real `rag-cli search ... | head -60` chain that tripped block_rag_cli_chained.py (non-rag-cli after rag-cli) — genuine hook prefix on the real tool_result."),
    (_MC, 128, 0, 62):  ('genuine CC injection', "Bash ran real `git config --global core.hooksPath; ...` — tripped block_git_destructive.py; genuine hook prefix."),
    (_MC, 202, 0, 97):  ('quoted data', "tool_use is `rag-cli search \"quoted system-reminder inside tool_result stripped false positive\" monitor-cc-docs --document 'process-docs/%'`. context_before is literally '## Task B — Env-context system-reminder ... CC injects this SR block on nearly every request:\\n```' and context_after continues '```\\n334 chars of inner text per request, never useful to the proxy model.' — a fenced EXAMPLE block inside a process-docs entry describing this very SR template, not a per-request CC injection into this tool_result."),
    (_MC, 249, 0, 119): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 264, 0, 126): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 270, 0, 129): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (this file is a LIVE, currently-growing session log — this row appeared between two runs of this script)."),
    (_MC, 300, 0, 143): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth as msg[270]; corpus keeps growing across re-runs during this report-framing fix)."),
    (_MC, 315, 0, 150): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 329, 0, 157): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 351, 0, 167): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 370, 0, 176): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_PO, 30, 0, 16):   ('genuine CC injection', "Bash ran real `rag-cli search ... monitor-cc-reference | head -60` — tripped block_rag_cli_chained.py; genuine hook prefix."),
    (_PO, 70, 0, 35):   ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 80, 0, 40):   ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 91, 0, 45):   ('genuine CC injection', "Real backgrounded `sleep 420` timer — genuine ack."),
    (_PO, 101, 0, 50):  ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 112, 0, 55):  ('genuine CC injection', "Real backgrounded `sleep 300` timer — genuine ack."),
    (_PO, 122, 0, 60):  ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 131, 0, 64):  ('genuine CC injection', "Real backgrounded `sleep 240` timer — genuine ack."),
    (_PO, 139, 0, 68):  ('genuine CC injection', "Real backgrounded `sleep 420` timer — genuine ack."),
    (_PO, 147, 0, 72):  ('genuine CC injection', "Real backgrounded `sleep 480` timer — genuine ack."),
    (_PO, 269, 0, 129): ('genuine CC injection', "Bash ran real `gh-cli index_issues ... | tail -20` — tripped block_gh_cli_chained.py; genuine hook prefix."),
    (_PO, 273, 0, 131): ('genuine CC injection', "Real backgrounded `gh-cli index_issues` — genuine ack."),
    (_W2, 11, 0, 7):    ('genuine CC injection', "Bash `cat vor-unterschrift.md; ...` real output exceeded persist threshold (52KB) — Preview section is the genuine persisted-output wrapper around real command output."),
    (_W2, 158, 0, 77):  ('genuine CC injection', "Bash ran real `grep -rn ruhig wohnungssuche/Meta/` — tripped block_broad_grep.py; genuine hook prefix."),
    (_W2, 604, 0, 291): ('genuine CC injection', "Bash `curl`-style page fetch loop, real output exceeded persist threshold (39.4KB) — genuine Preview section."),
    (_W2, 697, 0, 335): ('genuine CC injection', "Bash ran real `rag-cli list_collections --filter wise ...` chain — tripped block_rag_cli_chained.py; genuine hook prefix."),
    (_CR, 10, 0, 5):    ('genuine CC injection', "Bash `cat /tmp/tc_seed.html` real output (246323 bytes) exceeded persist threshold (240.6KB) — genuine Preview section of a real persisted-output wrapper."),
    (_CR, 58, 0, 27):   ('genuine CC injection', "Real backgrounded `rag-cli index --collection monitor-cc-reference` — genuine ack."),
}
