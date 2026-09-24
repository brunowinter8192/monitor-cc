# render_byte_identity declared as verification — 2026-09-24

Only a DOCS.md declaration was made. The harness prints one `HASH:` line and asserts nothing, so it is documented as a verification aid (a human compares two runs before and after a change) with the fact that decides its stability:

- Input is synthetic and built inline; two runs on the same tree give the same hash.
