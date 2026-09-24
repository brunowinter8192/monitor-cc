# m2_hover_timing report

Run: 2026-09-24T18:25:21
Old: git archive 0ce370df (0ce370df); new: worktree. Terminal patched to 120x45.
Each cell: median of 21 hover-triggered builds (one mouse-motion event then one full build of the pane output), ms of process CPU time (the machine is shared and heavily loaded, wall time varies up to 10x); cold = first build.
scale 10 = the real turn list repeated 10 times (synthetic, hypothesis for larger sessions).

| pane | session | scale | turns | calls | old cold | old hover median | new cold | new hover median | speedup |
|---|---|---|---|---|---|---|---|---|---|
| tokens | many_calls (35 turns, 869 calls) | 1 | 35 | 869 | 37.3 | 49.95 | 29.5 | 0.50 | 99.9x |
| tokens | many_calls (35 turns, 869 calls) | 10 | 350 | 8690 | 284.0 | 248.01 | 273.4 | 0.47 | 532.2x |
| tokens | many_turns (104 turns, 460 calls) | 1 | 104 | 460 | 18.3 | 15.48 | 15.4 | 0.40 | 38.2x |
| tokens | many_turns (104 turns, 460 calls) | 10 | 1040 | 4600 | 150.8 | 157.62 | 337.2 | 0.72 | 218.6x |
| worker_tokens | many_calls (35 turns, 869 calls) | 1 | 35 | 869 | 34.7 | 29.17 | 41.8 | 0.83 | 35.0x |
| worker_tokens | many_calls (35 turns, 869 calls) | 10 | 350 | 8690 | 495.6 | 259.06 | 244.2 | 0.45 | 577.0x |
| worker_tokens | many_turns (104 turns, 460 calls) | 1 | 104 | 460 | 15.2 | 15.10 | 15.6 | 0.40 | 37.9x |
| worker_tokens | many_turns (104 turns, 460 calls) | 10 | 1040 | 4600 | 146.5 | 141.76 | 145.5 | 0.42 | 335.1x |
