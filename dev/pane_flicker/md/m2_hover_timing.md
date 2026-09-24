# m2_hover_timing report

Run: 2026-09-24T18:17:16
Old: git archive integration (0ce370df); new: worktree. Terminal patched to 120x45.
Each cell: median of 21 hover-triggered builds (one mouse-motion event then one full build of the pane output), ms of process CPU time (the machine is shared and heavily loaded, wall time varies up to 10x); cold = first build.
scale 10 = the real turn list repeated 10 times (synthetic, hypothesis for larger sessions).

| pane | session | scale | turns | calls | old cold | old hover median | new cold | new hover median | speedup |
|---|---|---|---|---|---|---|---|---|---|
| tokens | many_calls (35 turns, 869 calls) | 1 | 35 | 869 | 47.7 | 47.11 | 48.0 | 0.66 | 71.9x |
| tokens | many_calls (35 turns, 869 calls) | 10 | 350 | 8690 | 268.6 | 250.96 | 277.6 | 0.56 | 449.8x |
| tokens | many_turns (104 turns, 460 calls) | 1 | 104 | 460 | 16.4 | 15.48 | 17.3 | 0.42 | 36.7x |
| tokens | many_turns (104 turns, 460 calls) | 10 | 1040 | 4600 | 164.1 | 226.67 | 278.6 | 1.15 | 197.8x |
| worker_tokens | many_calls (35 turns, 869 calls) | 1 | 35 | 869 | 45.2 | 53.72 | 60.2 | 0.80 | 67.4x |
| worker_tokens | many_calls (35 turns, 869 calls) | 10 | 350 | 8690 | 279.9 | 252.63 | 291.7 | 0.47 | 533.0x |
| worker_tokens | many_turns (104 turns, 460 calls) | 1 | 104 | 460 | 16.1 | 15.21 | 15.2 | 0.40 | 37.7x |
| worker_tokens | many_turns (104 turns, 460 calls) | 10 | 1040 | 4600 | 145.6 | 152.61 | 337.4 | 1.05 | 144.8x |
