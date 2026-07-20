# claude.exe high GPU load — session 2026-06-23

## Problem

Activity Monitor showed `claude.exe` (Apple type, despite `.exe` name — the CC binary) at **93.3% GPU**, 6.2% CPU, CPU-Zeit 6:36, ranking ABOVE a legit concurrent Python/MinerU convert (90.5% GPU). A Node-CLI pegging the GPU is anomalous. User note: not observed in prior 2.1.176 sessions — possibly new. Status: OBSERVE, no action taken yet (user watching).

CC binary: `CLAUDE_CODE_EXECPATH=/Users/brunowinter2000/cc-cache-fix-176/node_modules/@anthropic-ai/claude-code/bin/claude.exe` (a custom "cache-fix" build of 2.1.176).

## Investigation

### Process identification — CONFIRMED our session

- `$PPID` of the Bash shell = **2404**; PID 2404 is the orchestrator's claude.exe. Its CPU-Zeit (6:44 at check time) matches the screenshot's 6:36 (minutes older). → the 93% GPU process IS our session.
- 5 `claude.exe` processes total: 2404 (our orchestrator, 32% CPU at ps-time), 63155 + 72756 (workers, `--model sonnet --dangerously-skip-permissions`), 4687 + 48987 (other sessions). Only 2404 was GPU-active; siblings at 0% CPU / GPU-idle.

### CPU sample (`sample 2404 3`)

- Main thread: 2378/2554 samples in `kevent64` → event-loop idle/waiting. CPU is NOT the bottleneck.
- `sample` is a CPU sampler; GPU compute is async/off-CPU → does not appear in CPU stacks. The 93% GPU is real but invisible to `sample`.

### Loaded frameworks (sample image list)

Full Apple on-device ML / Vision / Metal / image stack mapped into 2404:
- Accelerate: `libBNNS` (Basic Neural Network Subroutines), libBLAS, libLAPACK, libvDSP, libLinearAlgebra, libSparse, libvMisc.
- MetalPerformanceShaders: `MPSNeuralNetwork`, `MetalPerformanceShadersGraph`, MPSMatrix, MPSNDArray, MPSImage, MPSRayIntersector, MPSCore.
- Vision: `libfaceCore`. ImageIO: libJPEG/libPng/libTIFF/libJP2/libGIF. RenderBox, OpenGL, GPUWrangler.
- One native Node addon: `/private/var/folders/*/.99bfcbebbbed46fb-00000000.node` (extracted-at-runtime, opaque hash name).

### CORRECTION — framework presence is NOT evidence of active ML

Initial read ("MPS loaded → on-device ML inference") was overstated. `vmmap` count of `MetalPerformanceShaders|libBNNS|Vision|ImageIO|.node` references per process:

| PID | role | count |
|---|---|---|
| 2404 | our session | 110 |
| 4687 | other session | 110 |
| 48987 | idle session | 88 |
| 72756 | worker | 88 |

The ML/Metal/Vision stack is **default CC linkage** (every session maps 88–110), likely via the native `.node` addon. Its presence does NOT indicate active ML. The +22 in image-handling sessions (2404, 4687) is extra ImageIO/Vision codecs loaded on demand.

### What remains solid

1. The 93% GPU process IS our session (2404).
2. Only our session is GPU-active; sibling claude.exe are GPU-idle → it is session-specific, not "CC always uses GPU".
3. CPU main-thread idle → genuine async GPU compute, not a CPU spin.
4. What the GPU is computing: UNKNOWN from here (per-process GPU breakdown needs `sudo powermetrics`, unavailable).

## Hypotheses

| Hypothesis | Status | Evidence |
|---|---|---|
| Image handling (pasted screenshots Image #2/#4/#5) triggers the Vision/ImageIO/MPS GPU path | Active / unverified | 2404 loaded +22 image/Vision libs vs idle sessions; consistent with image processing. BUT image decode is transient — does not obviously explain SUSTAINED 93%. |
| Stuck GPU job / leak in the cc-cache-fix-176 custom build | Unverified | Would be supported if GPU stays pegged with no new images. Needs observation. |
| Intended on-device ML feature | Weakened | Frameworks are default-loaded in all sessions → not evidence. |

## Open Questions

- Is the 93% GPU **sustained** (→ stuck job/leak, remedy = restart this CC session) or **transient** (drops without new images → harmless image decode)? Observable only in Activity Monitor (CLI per-process GPU needs sudo). User observing.
- What does the cc-cache-fix-176 custom build do — any on-device ML / GPU feature by design?
- Not seen in prior 176 sessions (user) → what is the session-specific trigger?
- Identity of the native `.node` addon (opaque hash name in /private/var/folders).
