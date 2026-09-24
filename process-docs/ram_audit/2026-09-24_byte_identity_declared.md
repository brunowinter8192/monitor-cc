# dump_byte_identity declared as verification — 2026-09-24

Only a DOCS.md declaration was made. The harness prints one `HASH:` line and asserts nothing, so it is documented as a verification aid (a human compares two runs before and after a change) with the fact that decides its stability:

- Synthetic input, but the run sends SIGUSR1 to itself, waits a fixed 0.2 s, writes into `dev/ram_audit/dumps/` and uses the fixed PID file `/tmp/.monitor_cc_pid_byteidentity`. Two concurrent runs collide; a slow machine can end with `no dump file was written`. No env seam exists. Not changed in this pass.
