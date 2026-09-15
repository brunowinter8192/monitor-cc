# P5 -- proxy pane message-row copy-by-click probe run (2026-09-15T19:24:51.917595+00:00)

**Result: 91/91 checks passed**

| Check | Result |
|---|---|
| both message rows keyed | PASS |
| both message rows registered as copy rows | PASS |
| REQ row still registered as a copy row too | PASS |
| msg[0] serialization non-empty | PASS |
| msg[1] serialization non-empty | PASS |
| msg[0] text appears verbatim inside the REQ-level copy | PASS |
| msg[1] text appears verbatim inside the REQ-level copy | PASS |
| msg[0] exact text | PASS |
| msg[1] exact text | PASS |
| main: click on msg row 0 copy column triggers copy | PASS |
| main: flash keyed by the msg's own key, not entry_idx | PASS |
| main: sibling msg row does NOT flash from this copy | PASS |
| main: click on msg row 1 copy column triggers copy | PASS |
| main: non-copy click on msg row returns no-change | PASS |
| main: non-copy click on msg row leaves expand_states untouched | PASS |
| main: non-copy click on msg row writes nothing to clipboard | PASS |
| main: REQ copy-click still fires | PASS |
| main: REQ flash keyed by entry_idx (unchanged) | PASS |
| worker: click on msg row 0 copy column triggers copy | PASS |
| worker: flash keyed by the msg's own key, not entry_idx | PASS |
| worker: sibling msg row does NOT flash from this copy | PASS |
| worker: click on msg row 1 copy column triggers copy | PASS |
| worker: non-copy click on msg row returns no-change | PASS |
| worker: non-copy click on msg row leaves expand_states untouched | PASS |
| worker: non-copy click on msg row writes nothing to clipboard | PASS |
| worker: REQ copy-click still fires | PASS |
| worker: REQ flash keyed by entry_idx (unchanged) | PASS |
| message keys still present at narrow width (rendering itself unaffected) | PASS |
| no msg row registered as a copy row at width=10 | PASS |
| thinking block keyed | PASS |
| thinking row registered as a copy row | PASS |
| sibling message row still registered as a copy row too | PASS |
| REQ row still registered as a copy row too | PASS |
| thinking row registered EVEN WHILE COLLAPSED (copy affordance is not gated on expand state) | PASS |
| thinking serialization non-empty | PASS |
| thinking text appears verbatim inside the message-level copy | PASS |
| thinking exact text | PASS |
| non-think/non-block key returns empty string (defensive dispatch) | PASS |
| main: click on thinking row copy column triggers copy | PASS |
| main: flash keyed by the thinking block's own key, not entry_idx or the msg key | PASS |
| main: non-copy click on thinking row still returns changed=True | PASS |
| main: non-copy click on thinking row TOGGLES expand_states (pre=False, post=True) | PASS |
| main: non-copy click on thinking row writes nothing to clipboard | PASS |
| main: a second non-copy click toggles back to the original state | PASS |
| main: copying the sibling message row does NOT flash the thinking row | PASS |
| worker: click on thinking row copy column triggers copy | PASS |
| worker: flash keyed by the thinking block's own key, not entry_idx or the msg key | PASS |
| worker: non-copy click on thinking row still returns changed=True | PASS |
| worker: non-copy click on thinking row TOGGLES expand_states (pre=False, post=True) | PASS |
| worker: non-copy click on thinking row writes nothing to clipboard | PASS |
| worker: a second non-copy click toggles back to the original state | PASS |
| worker: copying the sibling message row does NOT flash the thinking row | PASS |
| thinking key still present at narrow width (rendering itself unaffected) | PASS |
| no thinking row registered as a copy row at width=10 | PASS |
| both non-thinking blocks in msg[0] keyed | PASS |
| both block rows registered as copy rows | PASS |
| owning message row still registered as a copy row too | PASS |
| REQ row still registered as a copy row too | PASS |
| block[0] (text) serialization non-empty | PASS |
| block[1] (tool_use) serialization non-empty | PASS |
| block[0] exact text | PASS |
| block[1] exact text | PASS |
| block[0] text appears verbatim inside its message-level copy | PASS |
| block[1] text appears verbatim inside its message-level copy | PASS |
| block[0] text appears verbatim inside the REQ-level copy (not just via transitivity) | PASS |
| block[1] text appears verbatim inside the REQ-level copy (not just via transitivity) | PASS |
| non-think/non-block key returns empty string (defensive dispatch, shared serializer) | PASS |
| main: click on block row 0 copy column triggers copy | PASS |
| main: flash keyed by the block's own key, not entry_idx or the msg key | PASS |
| main: sibling block row does NOT flash from this copy | PASS |
| main: click on block row 1 copy column triggers copy | PASS |
| main: non-copy click on block row returns no-change | PASS |
| main: non-copy click on block row leaves expand_states untouched | PASS |
| main: non-copy click on block row writes nothing to clipboard | PASS |
| main: copying the owning message row does NOT flash block row 0 | PASS |
| main: copying the owning message row does NOT flash block row 1 | PASS |
| main: REQ copy-click still fires after block-row changes | PASS |
| main: REQ flash keyed by entry_idx (unchanged), not any block key | PASS |
| worker: click on block row 0 copy column triggers copy | PASS |
| worker: flash keyed by the block's own key, not entry_idx or the msg key | PASS |
| worker: sibling block row does NOT flash from this copy | PASS |
| worker: click on block row 1 copy column triggers copy | PASS |
| worker: non-copy click on block row returns no-change | PASS |
| worker: non-copy click on block row leaves expand_states untouched | PASS |
| worker: non-copy click on block row writes nothing to clipboard | PASS |
| worker: copying the owning message row does NOT flash block row 0 | PASS |
| worker: copying the owning message row does NOT flash block row 1 | PASS |
| worker: REQ copy-click still fires after block-row changes | PASS |
| worker: REQ flash keyed by entry_idx (unchanged), not any block key | PASS |
| block keys still present at narrow width (rendering itself unaffected) | PASS |
| no block row registered as a copy row at width=10 | PASS |
