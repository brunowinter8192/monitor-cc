# RAM Research for the Monitor_CC Pane Stack — 2026-04-25

Research notes from the session where we found our RAM diagnosis had been superficial (list-cap instead of the real causes: `f.read()` peak, O(N²) cumulative messages, pymalloc retention). Goal: collect concrete tools and patterns from the community BEFORE touching code again.

## mitmproxy/mitmproxy — direct stack match

**Issue [#4456](https://github.com/mitmproxy/mitmproxy/issues/4456) — "mitmdump memory usage is always constantly growing"** (33 comments, closed 2021)

Same stack, same problem: long-running mitmdump RSS grows ~500 MB/hour, sawtooth pattern until OOM or a manual restart. Several users report the same thing (#1447 closed, #2713 closed, #3191 closed, #6620 open, #7208 open, #7760 closed). It's not a single bug but a recurring class — long-running mitm setups hold flow objects in memory longer than expected.

### Lessons from #4456

mitmproxy holds ALL flows in RAM by design until they're written to disk or the process ends — this is intended behavior for UI/replay functions. Anyone who doesn't need that must explicitly release flows.

**`stream_large_bodies` config option:** above the threshold, response bodies are streamed instead of buffered. The example addon `examples/addons/http-stream-simple.py` (15 lines, in the mitmproxy repo) simply does this in the `responseheaders` hook:

```python
def responseheaders(flow):
    flow.response.stream = True
```

This eliminates body buffering entirely for ALL responses. Directly applicable to our `src/proxy/addon.py` because we persist bodies to JSONL and don't need them in memory after writing.

### Diagnostic Pattern — What We Did NOT Do

mhils (mitmproxy maintainer) recommended a SIGUSR1 handler in the addon. On signal, the following sequence runs:

```python
import collections, gc, signal
from mitmproxy import flow

def debug(*_):
    gc.collect()
    d = collections.Counter()
    for o in gc.get_objects():
        t = str(type(o))
        if "mitmproxy" in t:
            d[t] += 1
    for t, count in d.most_common(10):
        print(count, t)

    # Walk referrers from first Flow object up
    for obj in gc.get_objects():
        if isinstance(obj, flow.Flow):
            holder = {"val": obj}
            seen = {id(holder)}
            for _ in range(20):
                referrers = [val for val in gc.get_referrers(holder["val"])
                             if id(val) not in seen]
                seen.update(id(r) for r in referrers)
                if not referrers:
                    break
                print(f"  type={type(referrers[0]).__name__}")
                holder["val"] = referrers[0]
            break

def load(loader):
    signal.signal(signal.SIGUSR1, debug)
```

This gives you: a class distribution of mitmproxy objects (shows where the RAM is going) plus a reference chain from the first flow object upward (shows WHO holds the refs). In mhils's diagnosis it turned out: the `Save` addon hadn't discarded errored flows → fixed in #4461.

**Applied to us:** we can do the same in our pane processes. Add a SIGUSR1 handler that runs a class-count via `gc.get_objects()`, filtered on `Pair`/`HTTPFlow`/dict/etc. Plus a referrer walk to identify holders. 30 lines of code, 5 minutes of setup, gives direct insight into WHAT is eating RAM in the panes.

## Textualize/textual — GC pause during render

**Issue [#6381](https://github.com/Textualize/textual/issues/6381) — "MarkdownViewer stutters every 1-2s while scrolling — Python GC gen2 pause"** (9 comments, OPEN, 2026-02)

Symptom: UI freezes 50-200ms while scrolling, roughly every 1-2 seconds. Root cause: Python's cyclic GC (gen2). Workaround: `gc.disable()` at startup eliminates the pause entirely — with the trade-off that cyclic references must be managed manually or triggered via `gc.collect()` at non-blocking points.

**Applied to us:** plausible that our panes have the same effect with large retained object sets. Hover/click reacts with low latency thanks to D5 select-wake, but if gen2 runs mid-render, it blocks anyway. Two approaches to test:

```python
import gc

# Option A: gc off entirely, manually triggered in idle phases
gc.disable()
# ... in the idle zone of the poll loop:
if time_since_last_collect > 30:
    gc.collect()

# Option B: only delay gen2, let gen0/1 keep running
gc.set_threshold(700, 10, 100000)  # default is (700, 10, 10) — gen2 now very rare
```

## nicolargo/glances — long-running monitor TUI with RAM growth

**Issue [#1447](https://github.com/nicolargo/glances/issues/1447) — "Memory Leak"** (21 comments, closed)

Close to our class: a long-running Python monitor TUI with gradual RSS growth.

Lessons:
- **`memory_profiler`** (PyPI: `memory-profiler`) as a diagnostic tool: the `@profile` decorator outputs line-by-line memory allocation for a function. More granular than tracemalloc for the question "where exactly in this function does the allocation happen."
- A library swap brought real RSS reduction: `requests` → `urllib3` 1.24.1, `json` → `ujson`. Both standard libraries can have cumulative allocation patterns in long-running processes.
- Glances offers `--disable-history` as a RAM-bounded mode. Architecturally: the user decides whether history is needed. We could introduce an analogous `--no-history` flag or similar per pane.

## Diagnostic Tool Inventory — Everything We Didn't Touch

| Tool | Source | Purpose |
|---|---|---|
| `tracemalloc` | stdlib | Snapshot peak/current allocations, top allocators by file:line |
| `memory_profiler` with `@profile` | PyPI | Line-level memory allocation in a function |
| `gc.get_objects()` + `Counter` | stdlib | Class distribution of live objects |
| `gc.get_referrers()` walk | stdlib | Finds holders pinning an object |
| `objgraph` | PyPI | Visualizes reference cycles, top types growing over time |
| `pympler` | PyPI | Heap profiler with object-type-aware breakdown, leak detection |
| SIGUSR1 handler | mhils pattern | On-demand dump in the running process without a restart |

Had we tapped just ONE of these sources in phase 1, the O(N²) cumulative-messages root cause would have been visible immediately instead of only after several wrong iterations.

## Concrete Action Items for the Next RAM Investigation Session

1. Add a SIGUSR1 handler to `src/panes/waste_pane.py` (30 LOC). Measure WHAT is retained first, then fix.
2. Add `flow.response.stream = True` to the `responseheaders` hook in `src/proxy/addon.py` — eliminates body buffering for our mitmdump instance (separate problem from pane RAM, but a further win).
3. Test `gc.disable()` + manual `gc.collect()` in idle phases for warnings/waste panes — whether that noticeably reduces render stutter.
4. Run `memory_profiler` with `@profile` on `_parse_log_file`, `_scan_proxy_entries_for_errors`, `_merge_new_events` for a line-level allocation profile.
5. Architecturally: the glances-style "user-configurable no-history mode per pane" pattern for panes where history isn't strictly needed.

All five of these actions belong in one investigation-first session, BEFORE dispatching code workers again.
