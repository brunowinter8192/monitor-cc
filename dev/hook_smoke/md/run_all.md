# hook_smoke run_all

25/25 strands passed

## PASS _strand_test_bg_task_detection

  [OK  ] open path under session tasks dir -> True
  [OK  ] no open path for session -> False
  [OK  ] session-id prefix collision does not false-positive
  [OK  ] real subprocess writer: detected while open, not after
  [OK  ] lsof failure fails open, keeps prior snapshot
  [OK  ] TTL gate: second call inside window is a no-op

All 6 tests passed.

## PASS _strand_test_block_broad_find

  [OK  ] real incident: ~/.claude tree BLOCK: exit=2 (expected 2)
  [OK  ] home dir tilde BLOCK: exit=2 (expected 2)
  [OK  ] home dir trailing slash BLOCK: exit=2 (expected 2)
  [OK  ] home via $HOME BLOCK: exit=2 (expected 2)
  [OK  ] filesystem root BLOCK: exit=2 (expected 2)
  [OK  ] claude subtree: projects subdir BLOCK: exit=2 (expected 2)
  [OK  ] multiple roots: one broad BLOCK: exit=2 (expected 2)
  [OK  ] $HOME subpath: $HOME/.claude BLOCK: exit=2 (expected 2)
  [OK  ] real incident + head PASS: exit=0 (expected 0)
  [OK  ] home + head PASS: exit=0 (expected 0)
  [OK  ] root + head PASS: exit=0 (expected 0)
  [OK  ] home with maxdepth PASS: exit=0 (expected 0)
  [OK  ] claude root with maxdepth PASS: exit=0 (expected 0)
  [OK  ] relative src/ dir PASS: exit=0 (expected 0)
  [OK  ] dot root PASS: exit=0 (expected 0)
  [OK  ] specific project path PASS: exit=0 (expected 0)
  [OK  ] find in double-quoted echo PASS: exit=0 (expected 0)
  [OK  ] find in worker-cli send quoted arg PASS: exit=0 (expected 0)
  [OK  ] mdfind not matched PASS: exit=0 (expected 0)

All 19 tests passed.

## PASS _strand_test_block_broad_grep

  [OK  ] bare recursive no scope BLOCK: exit=2 (expected 2)
  [OK  ] recursive dot no scope BLOCK: exit=2 (expected 2)
  [OK  ] recursive tilde dir BLOCK: exit=2 (expected 2)
  [OK  ] piped to tee not head BLOCK: exit=2 (expected 2)
  [OK  ] piped to wc not head BLOCK: exit=2 (expected 2)
  [OK  ] recursive piped to head PASS: exit=0 (expected 0)
  [OK  ] recursive piped to head bare PASS: exit=0 (expected 0)
  [OK  ] recursive piped to head -N PASS: exit=0 (expected 0)
  [OK  ] recursive with redirect then head PASS: exit=0 (expected 0)
  [OK  ] head then further pipe PASS: exit=0 (expected 0)
  [OK  ] has --include scope PASS: exit=0 (expected 0)
  [OK  ] file-targeted extension PASS: exit=0 (expected 0)
  [OK  ] non-recursive PASS: exit=0 (expected 0)
  [OK  ] git grep exempt PASS: exit=0 (expected 0)
  [OK  ] grep in single-quoted string PASS: exit=0 (expected 0)
  [OK  ] grep in heredoc body PASS: exit=0 (expected 0)

All 16 tests passed.

## PASS _strand_test_block_chained_sleep

  [OK  ] canonical pass: exit=0 (expected 0)
  [OK  ] canonical float pass: exit=0 (expected 0)
  [OK  ] no sleep pass: exit=0 (expected 0)
  [OK  ] chained before sleep BLOCK: exit=2 (expected 2)
  [OK  ] non-echo-done cont BLOCK: exit=2 (expected 2)
  [OK  ] real sleep after quoted BLOCK: exit=2 (expected 2)
  [OK  ] heredoc quoted body PASS: exit=0 (expected 0)
  [OK  ] heredoc unquoted body PASS: exit=0 (expected 0)
  [OK  ] single-quoted sleep PASS: exit=0 (expected 0)
  [OK  ] double-quoted sleep PASS: exit=0 (expected 0)
  [OK  ] ANSI-C quote sleep PASS: exit=0 (expected 0)
  [OK  ] cmd-subst sleep BLOCK: exit=2 (expected 2)
  [OK  ] backtick sleep BLOCK: exit=2 (expected 2)

All 13 tests passed.

## PASS _strand_test_block_cli_chained

  [OK  ] rag-cli search piped to head BLOCK: exit=2 (expected 2)
  [OK  ] gh-cli get_file_content (unprotected subcommand) piped BLOCK — rule 1 is universal: exit=2 (expected 2)
  [OK  ] worker-cli kill (unprotected subcommand) piped BLOCK: exit=2 (expected 2)
  [OK  ] linkedin piped to head BLOCK: exit=2 (expected 2)
  [OK  ] penny-cli piped BLOCK: exit=2 (expected 2)
  [OK  ] duallog expand piped to head BLOCK: exit=2 (expected 2)
  [OK  ] reddit-cli search_subreddits piped BLOCK: exit=2 (expected 2)
  [OK  ] for-loop over get_issue, one iteration piped BLOCK: exit=2 (expected 2)
  [OK  ] rag-cli search redirect to file BLOCK: exit=2 (expected 2)
  [OK  ] gh-cli get_issue redirect BLOCK: exit=2 (expected 2)
  [OK  ] gh-cli list_issues 2>&1 alone (no pipe) BLOCK: exit=2 (expected 2)
  [OK  ] worker-cli capture redirect BLOCK: exit=2 (expected 2)
  [OK  ] websearch scrape_url_chromium redirect BLOCK (2026-09-06: table used to name a stale, non-existent subcommand `scrape_url` — this exact subcommand text is the real one, cli.py has carried it for a while): exit=2 (expected 2)
  [OK  ] websearch search_web redirect PASS (deliberately unprotected, real subcommand): exit=0 (expected 0)
  [OK  ] duallog sessions redirect BLOCK (every subcommand protected): exit=2 (expected 2)
  [OK  ] linkedin get_messages redirect BLOCK (every subcommand protected): exit=2 (expected 2)
  [OK  ] penny-cli redirect BLOCK (no subcommand, whole invocation protected): exit=2 (expected 2)
  [OK  ] reddit-cli search_subreddits redirect BLOCK: exit=2 (expected 2)
  [OK  ] bare 2> on protected subcommand does NOT count as a redirect PASS: exit=0 (expected 0)
  [OK  ] unprotected rag-cli index redirect stays allowed PASS (no readback): exit=0 (expected 0)
  [OK  ] unprotected worker-cli status redirect stays allowed PASS: exit=0 (expected 0)
  [OK  ] unprotected reddit-cli index_subreddits redirect stays allowed PASS: exit=0 (expected 0)
  [OK  ] the milestone's canonical incident BLOCK: exit=2 (expected 2)
  [OK  ] readback via head BLOCK: exit=2 (expected 2)
  [OK  ] readback via cat BLOCK: exit=2 (expected 2)
  [OK  ] readback of a DIFFERENT file PASS (no target match): exit=0 (expected 0)
  [OK  ] redirect with no same-call readback stays allowed PASS: exit=0 (expected 0)
  [OK  ] interpreter-path websearch scrape_url_chromium redirect BLOCK (the real incident, verbatim shape): exit=2 (expected 2)
  [OK  ] interpreter-path websearch scrape_url_chromium piped BLOCK (rule 1 applies to the interpreter form too): exit=2 (expected 2)
  [OK  ] interpreter-path gh-cli get_issue redirect BLOCK (mechanism generalizes beyond websearch — different tool, `.venv` not `venv`, absolute path, no leading cd): exit=2 (expected 2)
  [OK  ] interpreter-path websearch search_web (unprotected subcommand) redirect PASS: exit=0 (expected 0)
  [OK  ] interpreter-path with NO known project-dir marker PASS (a random project's own cli.py is not mistaken for one of the 5 policed CLIs): exit=0 (expected 0)
  [OK  ] mkdir before rag-cli index PASS (no allowlist of chain segments): exit=0 (expected 0)
  [OK  ] ls/echo before gh-cli get_issue PASS: exit=0 (expected 0)
  [OK  ] penny-cli chained with && PASS (isolation retired): exit=0 (expected 0)
  [OK  ] cd guard before rag-cli search PASS (no redirect, no pipe): exit=0 (expected 0)
  [OK  ] cross-CLI chain, both protected, no pipe/redirect PASS: exit=0 (expected 0)
  [OK  ] for-loop over get_issue with no pipe/redirect PASS: exit=0 (expected 0)
  [OK  ] duallog path-substring FP PASS (not a real duallog invocation): exit=0 (expected 0)
  [OK  ] worker-cli status/name substring PASS (not a real duallog invocation): exit=0 (expected 0)
  [OK  ] no known CLI at all PASS: exit=0 (expected 0)
  [OK  ] cwd-resolved interpreter redirect BLOCK (measured bypass 1: no dir name in the command, cwd is a websearch worktree): exit=2 (expected 2)
  [OK  ] cwd-resolved interpreter piped BLOCK (measured bypass 2: no dir name in the command, cwd is the rag-cli directory itself): exit=2 (expected 2)
  [OK  ] cwd-resolved: another project's own cli.py PASS (cwd matches none of the 5 known CLI directories, exactly like the 259 chore-tracker calls this must keep passing): exit=0 (expected 0)
  [OK  ] malformed stdin payload fails open: exit=0 (expected 0)

All 45 tests passed.

## PASS _strand_test_block_dangerous_kill

  [OK  ] pkill -f pattern BLOCK: exit=2 (expected 2)
  [OK  ] pkill -f at start BLOCK: exit=2 (expected 2)
  [OK  ] pgrep -f pipe kill BLOCK: exit=2 (expected 2)
  [OK  ] kill $(pgrep -f X) BLOCK: exit=2 (expected 2)
  [OK  ] ps grep kill chain BLOCK: exit=2 (expected 2)
  [OK  ] pkill -f in single-quoted string PASS: exit=0 (expected 0)
  [OK  ] pkill -f in double-quoted string PASS: exit=0 (expected 0)
  [OK  ] pkill -f in heredoc body PASS: exit=0 (expected 0)
  [OK  ] pkill -f in heredoc unquoted PASS: exit=0 (expected 0)
  [OK  ] pkill -x exact name PASS: exit=0 (expected 0)
  [OK  ] pkill no -f PASS: exit=0 (expected 0)
  [OK  ] kill numeric pid PASS: exit=0 (expected 0)
  [OK  ] kill signal pid PASS: exit=0 (expected 0)
  [OK  ] worker-cli kill PASS: exit=0 (expected 0)
  [OK  ] no kill at all PASS: exit=0 (expected 0)
  [OK  ] pkill -9 -f dolt sql-server double-quoted PASS: exit=0 (expected 0)
  [OK  ] pkill -f dolt sql-server single-quoted PASS: exit=0 (expected 0)
  [OK  ] mixed allowlisted + generic pkill -f BLOCK: exit=2 (expected 2)

All 18 tests passed.

## PASS _strand_test_block_gh_cli_local_path

  [OK  ] get_file_content with /Users/... path BLOCK: exit=2 (expected 2)
  [OK  ] get_file_content with ~/... path BLOCK: exit=2 (expected 2)
  [OK  ] download_files with an absolute repo-path positional BLOCK: exit=2 (expected 2)
  [OK  ] download_files with a ~/... path among multiple positionals BLOCK: exit=2 (expected 2)
  [OK  ] get_file_content local path with --limit flag before it BLOCK: exit=2 (expected 2)
  [OK  ] get_file_content with repo-relative path PASS: exit=0 (expected 0)
  [OK  ] download_files with repo paths + --dest /tmp/x PASS (the trap case): exit=0 (expected 0)
  [OK  ] download_files with --dest before the paths PASS (dest not treated as a path positional): exit=0 (expected 0)
  [OK  ] get_file_content with --metadata-only flag, repo-relative path PASS: exit=0 (expected 0)
  [OK  ] get_repo_tree untouched PASS: exit=0 (expected 0)
  [OK  ] index_issues untouched PASS: exit=0 (expected 0)
  [OK  ] repo_freshness untouched PASS: exit=0 (expected 0)
  [OK  ] non-gh-cli command untouched PASS: exit=0 (expected 0)
  [OK  ] pattern inside single-quotes PASS shell-stripped: exit=0 (expected 0)
  [OK  ] pattern inside heredoc body PASS shell-stripped: exit=0 (expected 0)

All 15 tests passed.

## PASS _strand_test_block_git_destructive

  [OK  ] FP minimal: git push -u + newline + [ -f file ] PASS: exit=0 (expected 0)
  [OK  ] FP actual recap: push + echo + file-test across lines PASS: exit=0 (expected 0)
  [OK  ] git push --force single-line BLOCK: exit=2 (expected 2)
  [OK  ] git push --force-with-lease BLOCK: exit=2 (expected 2)
  [OK  ] git push -f single-line BLOCK: exit=2 (expected 2)
  [OK  ] git push origin main --force BLOCK: exit=2 (expected 2)
  [OK  ] git -C /repo push -f BLOCK: exit=2 (expected 2)
  [OK  ] git commit --amend BLOCK: exit=2 (expected 2)
  [OK  ] git commit --amend --no-edit BLOCK: exit=2 (expected 2)
  [OK  ] git commit --no-verify BLOCK: exit=2 (expected 2)
  [OK  ] git push --no-verify BLOCK: exit=2 (expected 2)
  [OK  ] git commit --allow-empty BLOCK: exit=2 (expected 2)
  [OK  ] git config write user.email BLOCK: exit=2 (expected 2)
  [OK  ] git -C /repo config write BLOCK: exit=2 (expected 2)
  [OK  ] git push plain PASS: exit=0 (expected 0)
  [OK  ] git push -u origin main single-line PASS: exit=0 (expected 0)
  [OK  ] git commit -m normal PASS: exit=0 (expected 0)
  [OK  ] git config --list read-only PASS: exit=0 (expected 0)
  [OK  ] git config --get read-only PASS: exit=0 (expected 0)
  [OK  ] git config --show-origin read-only PASS: exit=0 (expected 0)
  [OK  ] push --force in quoted commit message PASS: exit=0 (expected 0)

All 21 tests passed.

## PASS _strand_test_block_manual_worker_cleanup

  [OK  ] tmux kill-session full worker session name BLOCK: exit=2 (expected 2)
  [OK  ] tmux kill-session short worker name BLOCK: exit=2 (expected 2)
  [OK  ] tmux kill-session extra flag before -t BLOCK: exit=2 (expected 2)
  [OK  ] tmux kill-session no space after -t BLOCK: exit=2 (expected 2)
  [OK  ] git worktree remove relative path BLOCK: exit=2 (expected 2)
  [OK  ] git worktree remove absolute path BLOCK: exit=2 (expected 2)
  [OK  ] git -C worktree remove worker path BLOCK: exit=2 (expected 2)
  [OK  ] git worktree remove --force BLOCK: exit=2 (expected 2)
  [OK  ] worker-cli kill is allowed PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session non-worker session PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session regular session name PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session no -t arg PASS: exit=0 (expected 0)
  [OK  ] git worktree remove non-claude path PASS: exit=0 (expected 0)
  [OK  ] git worktree list PASS: exit=0 (expected 0)
  [OK  ] git worktree add PASS: exit=0 (expected 0)
  [OK  ] git branch -D allowed PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session worker in single-quoted message PASS: exit=0 (expected 0)
  [OK  ] git worktree remove in double-quoted message PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session separator blocks bridge PASS: exit=0 (expected 0)
  [OK  ] git worktree remove separator blocks bridge PASS: exit=0 (expected 0)
  [OK  ] tmux kill-session worker in comment PASS: exit=0 (expected 0)

All 21 tests passed.

## PASS _strand_test_block_non_canonical_edit

  [OK  ] sed -i on existing file BLOCK: exit=2 (expected 2)
  [OK  ] perl -pi on existing file BLOCK: exit=2 (expected 2)
  [OK  ] gawk -i inplace on existing file BLOCK: exit=2 (expected 2)
  [OK  ] python open() mode r+ on existing file BLOCK: exit=2 (expected 2)
  [OK  ] cat > truncating an existing file BLOCK: exit=2 (expected 2)
  [OK  ] python open() mode w on existing file, -c form BLOCK: exit=2 (expected 2)
  [OK  ] non-canonical python heredoc (wrong delimiter) on existing file BLOCK: exit=2 (expected 2)
  [OK  ] tee (no -a) on existing file BLOCK: exit=2 (expected 2)
  [OK  ] cat > creating a brand-new file PASS: exit=0 (expected 0)
  [OK  ] cat >> appending an existing file PASS: exit=0 (expected 0)
  [OK  ] tee -a an existing file PASS: exit=0 (expected 0)
  [OK  ] python open() mode x on a brand-new file PASS: exit=0 (expected 0)
  [OK  ] python open() mode w on a brand-new file PASS: exit=0 (expected 0)
  [OK  ] the exact canonical LINEEDIT form on an existing file PASS: exit=0 (expected 0)
  [OK  ] unresolvable path (sys.argv) PASS: exit=0 (expected 0)
  [OK  ] sed -i mentioned only as prose inside a new-file heredoc PASS: exit=0 (expected 0)
  [OK  ] sed -i mentioned only as a quoted search term PASS: exit=0 (expected 0)
  [OK  ] parse-error fail-open PASS: exit=0 (expected 0)

All 18 tests passed.

## PASS _strand_test_block_po_read

  [OK  ] head on PO export BLOCK: exit=2 (expected 2)
  [OK  ] tail on PO export BLOCK: exit=2 (expected 2)
  [OK  ] grep on PO export BLOCK: exit=2 (expected 2)
  [OK  ] cat on PO export BLOCK: exit=2 (expected 2)
  [OK  ] sed on PO export BLOCK: exit=2 (expected 2)
  [OK  ] rg on PO export BLOCK: exit=2 (expected 2)
  [OK  ] piped cat-to-head BLOCK: exit=2 (expected 2)
  [OK  ] split on PO export BLOCK: exit=2 (expected 2)
  [OK  ] dd on PO export BLOCK: exit=2 (expected 2)
  [OK  ] head on normal file PASS: exit=0 (expected 0)
  [OK  ] grep on .log file PASS: exit=0 (expected 0)
  [OK  ] cat on /tmp/foo.txt not under .claude PASS: exit=0 (expected 0)
  [OK  ] cat on .claude path not ending .txt PASS: exit=0 (expected 0)
  [OK  ] redirect-write to PO path not a read PASS: exit=0 (expected 0)
  [OK  ] PO path only in quoted string PASS: exit=0 (expected 0)
  [OK  ] real PO export AT boundary (50,000B) BLOCK: exit=2 (expected 2)
  [OK  ] real PO export ONE BYTE OVER boundary (50,001B) PASS: exit=0 (expected 0)
  [OK  ] dd if= on real PO export over boundary PASS (proves if= prefix is stripped before stat): exit=0 (expected 0)
  [OK  ] parse-error fail-open PASS: exit=0 (expected 0)

All 19 tests passed.

## PASS _strand_test_block_rag_cli_document_repeat

  [OK  ] single --document call ALLOW: exit=0 (expected 0)
  [OK  ] 1st --document call ALLOW: exit=0 (expected 0)
  [OK  ] 2nd --document call (same collection) BLOCK: exit=2 (expected 2)
  [OK  ] 3x collection-wide index call ALLOW: exits=[0, 0, 0] (expected all 0)
  [OK  ] cross-session independence: sess-A#1=0, sess-B#1=0, sess-A#2=2 (expected 0, 0, 2)
  [OK  ] delete subcommand 2nd call BLOCK: exits=0,2 (expected 0,2)
  [OK  ] malformed stdin fail-open: exit=0 (expected 0)

All rag-cli document-repeat tests passed.

## PASS _strand_test_block_rag_cli_index_isolated

  [OK  ] observed tail+echo+cd+index BLOCK: exit=2 (expected 2)
  [OK  ] tail before index && BLOCK: exit=2 (expected 2)
  [OK  ] index then echo && BLOCK: exit=2 (expected 2)
  [OK  ] index then tail ; BLOCK: exit=2 (expected 2)
  [OK  ] second rag-cli command alongside index BLOCK: exit=2 (expected 2)
  [OK  ] index piped to tee BLOCK: exit=2 (expected 2)
  [OK  ] tail before env-prefixed index BLOCK: exit=2 (expected 2)
  [OK  ] env-prefixed index then echo BLOCK: exit=2 (expected 2)
  [OK  ] multi-env-prefixed index piped to tee BLOCK: exit=2 (expected 2)
  [OK  ] assignment line + tail + cd + env-prefixed index BLOCK: exit=2 (expected 2)
  [OK  ] cmd subst in assignment value BLOCK: exit=2 (expected 2)
  [OK  ] backtick subst in assignment value BLOCK: exit=2 (expected 2)
  [OK  ] cmd subst in --collection argument BLOCK: exit=2 (expected 2)
  [OK  ] process substitution on redirect target BLOCK: exit=2 (expected 2)
  [OK  ] process substitution as input BLOCK: exit=2 (expected 2)
  [OK  ] arithmetic expansion in assignment value BLOCK: exit=2 (expected 2)
  [OK  ] cmd subst inside double-quoted cd target BLOCK: exit=2 (expected 2)
  [OK  ] backtick inside redirect filename BLOCK: exit=2 (expected 2)
  [OK  ] bare & no trailing space smuggling BLOCK: exit=2 (expected 2)
  [OK  ] bare & no spaces at all smuggling BLOCK: exit=2 (expected 2)
  [OK  ] bare index ALLOW: exit=0 (expected 0)
  [OK  ] index redirected to log ALLOW: exit=0 (expected 0)
  [OK  ] cd before index ALLOW: exit=0 (expected 0)
  [OK  ] cd before index with redirect ALLOW: exit=0 (expected 0)
  [OK  ] env-prefixed bare index ALLOW: exit=0 (expected 0)
  [OK  ] assignment line + cd + env-prefixed index + line-continued redirect ALLOW: exit=0 (expected 0)
  [OK  ] assignment line + cd + bare index + redirect ALLOW: exit=0 (expected 0)
  [OK  ] bare index with backslash line-continued redirect ALLOW: exit=0 (expected 0)
  [OK  ] quoted semicolon in assignment value ALLOW: exit=0 (expected 0)
  [OK  ] plain $VAR expansion in cd target is not command substitution ALLOW: exit=0 (expected 0)
  [OK  ] &> redirect not mistaken for background-& separator ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli search out of scope ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli list_documents out of scope ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli delete out of scope ALLOW: exit=0 (expected 0)
  [OK  ] no rag-cli ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli index inside single-quotes ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli index inside heredoc body ALLOW: exit=0 (expected 0)

All 37 tests passed.

## PASS _strand_test_block_rag_corpus_read

  [OK  ] cat over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] grep -r over the corpus tree BLOCK: exit=2 (expected 2)
  [OK  ] head over a quoted corpus path BLOCK: exit=2 (expected 2)
  [OK  ] tail over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] sed over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] awk over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] rg over the corpus tree BLOCK: exit=2 (expected 2)
  [OK  ] less over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] more over a corpus document BLOCK: exit=2 (expected 2)
  [OK  ] cat with the corpus path as a non-first argument BLOCK: exit=2 (expected 2)
  [OK  ] only a quoted corpus path argument BLOCK: exit=2 (expected 2)
  [OK  ] real rag-cli invocation chained with a corpus-read segment BLOCK (the corpus-read segment blocks regardless of what else is chained): exit=2 (expected 2)
  [OK  ] renamed checkout (rag-cli-eval) still blocks BLOCK (glob dodge): exit=2 (expected 2)
  [OK  ] renamed worktree (rag-cli-convert) still blocks BLOCK (glob dodge): exit=2 (expected 2)
  [OK  ] ls over the corpus tree ALLOW (management, not a content read): exit=0 (expected 0)
  [OK  ] rm over a corpus document ALLOW (deletion is sanctioned): exit=0 (expected 0)
  [OK  ] mv within the corpus tree ALLOW: exit=0 (expected 0)
  [OK  ] mkdir under the corpus tree ALLOW: exit=0 (expected 0)
  [OK  ] cat on an unrelated file ALLOW: exit=0 (expected 0)
  [OK  ] grep on an unrelated file ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli search standalone ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli read_document standalone ALLOW: exit=0 (expected 0)
  [OK  ] quoted mention inside echo ALLOW (not an actual read): exit=0 (expected 0)
  [OK  ] corpus-path text inside a heredoc body ALLOW (shell-strip blanks it before matching): exit=0 (expected 0)
  [OK  ] relative corpus path with no rag-* prefix in the text ALLOW (text-only limitation): exit=0 (expected 0)
  [OK  ] malformed stdin payload fails open: exit=0 (expected 0)
  [OK  ] block message: names rag-cli search as the allowed form
  [OK  ] block message: names rag-cli read_document as the allowed form
  [OK  ] block message: states file management stays allowed

All 29 tests passed.

## PASS _strand_test_block_rag_docs_layer

  [OK  ] docs collection no filter BLOCK: exit=2 (expected 2)
  [OK  ] docs collection after cd BLOCK: exit=2 (expected 2)
  [OK  ] docs collection with unrelated code subpath filter BLOCK: exit=2 (expected 2)
  [OK  ] docs collection --document process-docs ALLOW: exit=0 (expected 0)
  [OK  ] docs collection --exclude process-docs ALLOW: exit=0 (expected 0)
  [OK  ] docs collection --document= equals form ALLOW: exit=0 (expected 0)
  [OK  ] docs collection --document specific area ALLOW: exit=0 (expected 0)
  [OK  ] reference collection ALLOW: exit=0 (expected 0)
  [OK  ] list_documents ALLOW: exit=0 (expected 0)
  [OK  ] no rag-cli ALLOW: exit=0 (expected 0)
  [OK  ] rag-cli inside single-quotes ALLOW: exit=0 (expected 0)

All 11 tests passed.

## PASS _strand_test_block_unauthorized_background

  [OK  ] sleep N && echo done — sleep-only form ALLOW: rewritten_bg=None (expected None)
  [OK  ] sleep N bare — sleep-only form ALLOW: rewritten_bg=None (expected None)
  [OK  ] sleep N with custom echo text (fire-log actual) ALLOW: rewritten_bg=None (expected None)
  [OK  ] worker-cli wait bare ALLOW: rewritten_bg=None (expected None)
  [OK  ] worker-cli wait with project_path ALLOW: rewritten_bg=None (expected None)
  [OK  ] worker-cli wait with --timeout ALLOW: rewritten_bg=None (expected None)
  [OK  ] worker-cli wait with project_path + --timeout ALLOW: rewritten_bg=None (expected None)
  [OK  ] reddit-cli index_subreddits — foreground-forced FORCE: rewritten_bg=False (expected False)
  [OK  ] workflow.py index-dir — foreground-forced FORCE: rewritten_bg=False (expected False)
  [OK  ] ./venv/bin/python script.py — non-canonical background FORCE: rewritten_bg=False (expected False)
  [OK  ] rag-cli update_docs — original triggering incident FORCE: rewritten_bg=False (expected False)
  [OK  ] worker-cli waitfoo — not a word-boundary match on 'wait' FORCE: rewritten_bg=False (expected False)
  [OK  ] worker-cli wait && rag-cli index — mentions wait, this hook has no opinion (rewrite_worker_wait.py decides instead) NO-OP: rewritten_bg=None (expected None)
  [OK  ] cd /tmp; worker-cli wait — mentions wait, this hook has no opinion NO-OP: rewritten_bg=None (expected None)
  [OK  ] worker-cli wait mentioned only inside a quoted echo argument does NOT exempt an unrelated non-canonical command FORCE: rewritten_bg=False (expected False)
  [OK  ] ./venv/bin/python script.py foreground — no output PASS: rewritten_bg=None (expected None)

All 16 tests passed.

## PASS _strand_test_block_worker_kill_while_working

[PASS] kill working → block (blocking: foo)
[PASS] kill idle → allow
[PASS] kill force-stopped idle (no pct) → allow
[PASS] kill exited → allow
[PASS] kill unknown → allow
[PASS] kill nonexistent (empty status) → allow
[PASS] quoted kill inside send-message → allow (double-quoted region stripped)
[PASS] heredoc kill inside send-message → allow (heredoc body stripped)
[PASS] non-kill command → allow
[PASS] multi-kill one working → block (bar) (blocking: bar)
[PASS] status_fn raises → allow (exception treated as empty status)
[PASS] kill working 100% → block (blocking: foo)
[PASS] known accepted residual: comment carrying kill+working-name → block (blocking: foo)

13/13 passed

## PASS _strand_test_block_worker_send_while_working

[PASS] send working → block (blocking: foo)
[PASS] send idle → allow
[PASS] send dead → allow
[PASS] send unknown worker name (empty status) → allow
[PASS] quoted send inside another send-message → allow (double-quoted region stripped)
[PASS] heredoc send inside send-message → allow (heredoc body stripped)
[PASS] non-send command → allow
[PASS] multi-send one working → block (bar) (blocking: bar)
[PASS] status_fn raises → allow (exception treated as empty status)
[PASS] send working 100% → block (blocking: foo)
[PASS] malformed stdin payload fails open: exit=0 (expected 0)
[PASS] real entrypoint, no resolvable worker status: exit=0 (expected 0)

12/12 passed

## PASS _strand_test_fire_log

  [OK  ] block fire: decision=block, hook=block_noop_edit, tool=Edit
  [OK  ] rewrite fire: decision=rewrite, command+rewritten both present
  [OK  ] env-var override: log written to custom path, canonical untouched, control run reaches canonical

All fire-log tests passed.

## PASS _strand_test_hook_setup_main_branch_gate

[PASS] all on main + all in tree -> all installed, none skipped
[PASS] one absent from main -> skipped, rest installed
[PASS] git query fails (None) -> fail-safe skip, rest installed
[PASS] mixed: present + absent + query-error in one set
[PASS] same script, multiple matchers, absent from main -> ALL its entries skipped
[PASS] on main but missing from the working tree -> skipped, rest installed
[PASS] on main AND present in tree -> installed (mirror-image positive)
[PASS] missing from BOTH main and the working tree -> skipped (main-branch reason primary)
[PASS] absent script skips EVERY matcher entry, not just the first
[PASS] skip reason text distinguishes not-on-main vs missing-from-tree

10/10 passed

## PASS _strand_test_hook_trace_lines

[PASS] case_parse_error_all_hooks
[PASS] case_log_dir_created
[PASS] case_log_write_failure_stderr
[PASS] case_strip_raw_fallback
[PASS] case_unterminated_quote
[PASS] case_shlex_exempt
[PASS] case_po_read_unknown_size
[PASS] case_rag_state_corrupt_line
[PASS] case_rag_state_unreadable
[PASS] case_worker_cli_missing
[PASS] case_worker_cli_rc
[PASS] case_worker_cli_timeout
[PASS] case_status_fn_raises
[PASS] case_getcwd_failed
[PASS] case_sweep_prints
[PASS] case_null_byte_read_path
[PASS] case_unpack_entry_gone

17/17 passed

## PASS _strand_test_log_janitor

  [OK  ] old record >7 days → dropped
  [OK  ] recent record <7 days → kept
  [OK  ] empty ts → kept (fail-safe)
  [OK  ] naive ts no TZ → kept (fail-safe)

All 4 tests passed.

## PASS _strand_test_rewrite_background_sleep

  [OK  ] sleep 300 background timer → rewrite to worker-cli wait
  [OK  ] sleep 5 background timer → rewrite to worker-cli wait
  [OK  ] sleep 1200 background timer → rewrite to worker-cli wait
  [OK  ] old canonical sleep 3300 && echo done — also a stale habit now, rewrite
  [OK  ] bare sleep 300 — bare sleep, rewrite to worker-cli wait
  [OK  ] sleep 45 with custom echo text (fire-log actual incident) → rewrite
  [OK  ] foreground sleep 300 — no background flag, no rewrite
  [OK  ] worker-cli wait bare — already canonical, no rewrite
  [OK  ] worker-cli wait with project_path + --timeout — already canonical, no rewrite
  [OK  ] rag-cli background — not canonical form, no rewrite
  [OK  ] sleep 300 && rag-cli — not echo done form, no rewrite
  [OK  ] bare sleep 300 from a WORKTREE cwd — orchestrator-only guard, no rewrite
  [OK  ] sleep 3300 && echo done from a WORKTREE cwd — old canonical form, still no rewrite
  [OK  ] foreground sleep from a WORKTREE cwd — no rewrite (already a no-op via the bg-flag gate)

All 14 tests passed.

## PASS _strand_test_rewrite_chained_sleep

  [OK  ] echo marker then sleep then tmux — strip sleep
  [OK  ] echo X && sleep then bd — strip sleep
  [OK  ] true guard before sleep then bd — strip sleep
  [OK  ] kill before sleep — load-bearing, no strip
  [OK  ] launchctl before sleep — load-bearing, no strip
  [OK  ] sleep inside for...done loop — no strip
  [OK  ] canonical sleep N && echo done — no strip
  [OK  ] sleep-first leading timer intent — no strip
  [OK  ] grep before sleep — strip
  [OK  ] cat before sleep — strip
  [OK  ] ls before sleep — strip
  [OK  ] wc before sleep — strip
  [OK  ] head before sleep — strip
  [OK  ] tail before sleep — strip
  [OK  ] find before sleep — strip
  [OK  ] git status before sleep — strip
  [OK  ] git log before sleep — strip
  [OK  ] git diff before sleep — strip
  [OK  ] git show before sleep — strip
  [OK  ] rag-cli search before sleep — strip
  [OK  ] worker-cli status before sleep — strip
  [OK  ] worker-cli list before sleep — strip
  [OK  ] worker-cli response before sleep — strip
  [OK  ] git push before sleep — load-bearing, no strip
  [OK  ] git pull before sleep — load-bearing, no strip
  [OK  ] rag-cli index before sleep — load-bearing, no strip
  [OK  ] rag-cli update_docs before sleep — load-bearing, no strip
  [OK  ] worker-cli send before sleep — load-bearing, no strip
  [OK  ] worker-cli kill before sleep — load-bearing, no strip
  [OK  ] tail -f log backgrounded & sleep — not a chain op, no strip
  [OK  ] git -C <path> status — flag between cmd and subcmd, conservatively no strip

All 31 tests passed.

## PASS _strand_test_rewrite_worker_wait

  [OK  ] bare worker-cli wait, run_in_background true — already correct NO-OP
  [OK  ] bare with --timeout, run_in_background true — already correct NO-OP
  [OK  ] bare with project_path, run_in_background true — already correct NO-OP
  [OK  ] bare with project_path + --timeout, run_in_background true — already correct NO-OP
  [OK  ] rewrite_background_sleep.py's own output — already correct NO-OP
  [OK  ] bare worker-cli wait, run_in_background false — flag forced REWRITE
  [OK  ] bare worker-cli wait, run_in_background omitted — flag forced REWRITE
  [OK  ] bare with --timeout, run_in_background false — flag forced, command unchanged REWRITE
  [OK  ] cd ; worker-cli wait, no path of its own — path injected, flag forced REWRITE (the actual incident shape)
  [OK  ] cd && worker-cli wait, no path of its own — path injected REWRITE
  [OK  ] cd ; worker-cli wait, run_in_background false too — both forced in one payload REWRITE
  [OK  ] cd ; worker-cli wait --timeout 600, no path of its own — path injected before the flag REWRITE
  [OK  ] cd ; worker-cli wait already has its own path — cd dropped as redundant REWRITE
  [OK  ] cd \n worker-cli wait (newline separator, real spawn-cd-prefix shape) REWRITE
  [OK  ] worker-cli wait && rag-cli index docs — trailing chain, unfixable BLOCK
  [OK  ] worker-cli wait ; echo done — trailing chain, unfixable BLOCK
  [OK  ] worker-cli wait piped — unfixable BLOCK
  [OK  ] cd /tmp && worker-cli wait && echo done — cd AND trailing chain, unfixable BLOCK
  [OK  ] worker-cli waitfoo — not a word-boundary match NO-OP
  [OK  ] unrelated command NO-OP
  [OK  ] worker-cli wait mentioned only inside a quoted send message NO-OP
  [OK  ] worker-cli wait mentioned only inside a heredoc body NO-OP

All 22 tests passed.
