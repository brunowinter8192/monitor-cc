# dev/cc_internals/

## Role
Research artifacts from Claude Code binary and source analysis: env-var inventories extracted from npm binaries and cross-referenced against community decompile repos. Add a new dated file under `md/` when extracting from a new binary version. No scripts live here.

## Public Interface
No `__init__.py` and no `.py` files. The directory holds Markdown reports under `md/` only.

## Flow
A binary version is inspected by hand, the findings are written as one dated report under `md/`, and the report is read by later sessions. No processing chain exists.

## Modules
None. `md/20260428_env_var_inventory_v2.1.121.md` is a standalone report with no producing script. Sources and method are in the process-docs of this area.

## State
None.
