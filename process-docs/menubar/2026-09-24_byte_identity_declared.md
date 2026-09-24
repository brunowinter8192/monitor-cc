# Menubar byte-identity harnesses declared as verification — 2026-09-24

Only a DOCS.md declaration was made. The harness prints one `HASH:` line and asserts nothing, so it is documented as a verification aid (a human compares two runs before and after a change) with the fact that decides its stability:

- `discover_byte_identity.py` and `panel_manager_byte_identity.py`: synthetic inline input, stable hash.
- `model_controller_byte_identity.py`: seeds one check from the real `~/.claude/shared-rules/proxy_rules.json`, no env seam, so a changed rules file changes the hash.
