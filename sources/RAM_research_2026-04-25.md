# RAM-Research für Monitor_CC Pane-Stack — 2026-04-25

Recherche-Notizen aus der Session in der wir festgestellt haben dass unsere RAM-Diagnose oberflächlich war (Listen-Cap statt der echten Ursachen: `f.read()`-Peak, O(N²) cumulative messages, pymalloc-Retention). Ziel: konkrete Tools und Patterns aus der Community sammeln BEVOR wir wieder Code anfassen.

## mitmproxy/mitmproxy — direkter Stack-Match

**Issue [#4456](https://github.com/mitmproxy/mitmproxy/issues/4456) — "mitmdump memory usage is always constantly growing"** (33 Kommentare, closed 2021)

Gleicher Stack, gleiches Problem: long-running mitmdump RSS wächst ~500 MB/Stunde, sägezahn-Pattern bis OOM oder manueller Restart. Mehrere User berichten dasselbe (#1447 closed, #2713 closed, #3191 closed, #6620 open, #7208 open, #7760 closed). Es ist kein einzelner Bug, sondern eine wiederkehrende Klasse — long-running mitm-Setups halten Flow-Objekte länger als erwartet im Speicher.

### Lessons aus #4456

mitmproxy hält per Design ALLE Flows im RAM bis sie auf Disk geschrieben sind oder der Prozess endet — das ist beabsichtigtes Verhalten für UI/Replay-Funktionen. Wer das nicht braucht, muss explizit Flows freigeben.

**`stream_large_bodies` config option:** oberhalb der Schwelle werden response bodies gestreamt statt gepuffert. Das Beispiel-Addon `examples/addons/http-stream-simple.py` (15 Zeilen, im mitmproxy repo) macht im `responseheaders`-Hook einfach:

```python
def responseheaders(flow):
    flow.response.stream = True
```

Das eliminiert Body-Buffering komplett für ALLE responses. Direkt anwendbar auf unser `src/proxy/addon.py` weil wir Bodies in JSONL persistieren und nach dem Schreiben nicht mehr im Speicher brauchen.

### Diagnose-Pattern — das was wir nicht gemacht haben

mhils (mitmproxy maintainer) hat einen SIGUSR1-Handler im Addon empfohlen. Bei Signal-Eingang läuft folgende Sequenz:

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

Das gibt dir: Klassen-Verteilung der mitmproxy-Objekte (zeigt wo das RAM hin wandert) plus Reference-Chain vom ersten Flow-Object aufwärts (zeigt WER die Refs hält). Bei mhils' Diagnose hat sich rausgestellt: das `Save`-Addon hat errored Flows nicht discarded → fix in #4461.

**Übertragen auf uns:** wir können dasselbe in unseren Pane-Prozessen machen. SIGUSR1-Handler einbauen der Counter-by-class über `gc.get_objects()` läuft, gefiltert auf `Pair`/`HTTPFlow`/Dict/etc. Plus Referrer-Walk um Holder zu identifizieren. 30 Zeilen Code, 5 Minuten Setup, bringt direkten Aufschluss WAS in den Panes RAM frisst.

## Textualize/textual — GC pause beim Render

**Issue [#6381](https://github.com/Textualize/textual/issues/6381) — "MarkdownViewer stutters every 1-2s while scrolling — Python GC gen2 pause"** (9 Kommentare, OPEN, 2026-02)

Symptom: UI freezed 50–200ms beim Scrollen, ungefähr alle 1-2 Sekunden. Root cause: Python's cyclic GC (gen2). Workaround: `gc.disable()` beim Startup eliminiert die Pause vollständig — mit dem Trade-off dass cyclic references manuell gemanaged werden müssen oder per `gc.collect()` an non-blocking Zeitpunkten getriggert.

**Übertragen auf uns:** plausibel dass unsere Panes mit großen retained Object-Sets denselben Effekt haben. Hover/Click reagiert dann zwar latenz-arm dank D5 select-wake, aber wenn gen2 mid-render läuft, blockiert es trotzdem. Zwei Ansätze testbar:

```python
import gc

# Option A: gc komplett aus, manuell triggern in idle phasen
gc.disable()
# ... in der idle-zone des poll loops:
if time_since_last_collect > 30:
    gc.collect()

# Option B: nur gen2 verzögern, gen0/1 weiter laufen
gc.set_threshold(700, 10, 100000)  # default ist (700, 10, 10) — gen2 nun sehr selten
```

## nicolargo/glances — long-running monitor TUI mit RAM-Wachstum

**Issue [#1447](https://github.com/nicolargo/glances/issues/1447) — "Memory Leak"** (21 Kommentare, closed)

Nah an unserer Klasse: long-running Python-Monitor-TUI mit graduellem RSS-Wachstum.

Lessons:
- **`memory_profiler`** (PyPI: `memory-profiler`) als Diagnose-Tool: `@profile` Decorator gibt Zeile-für-Zeile Memory-Allocation aus für eine Funktion. Granularer als tracemalloc für die Frage "wo genau in dieser Funktion wird allokiert".
- Library-Swap brachte real RSS-Reduktion: `requests` → `urllib3` 1.24.1, `json` → `ujson`. Beide Standard-Bibliotheken können in long-running Prozessen kumulative Allokations-Patterns haben.
- Glances bietet `--disable-history` als RAM-bounded-Mode. Architektonisch: User entscheidet ob Historie gebraucht wird. Wir könnten analog pro Pane einen `--no-history` Flag oder ähnliches einführen.

## Diagnose-Tool-Inventar — was wir alles nicht angefasst haben

| Tool | Quelle | Zweck |
|---|---|---|
| `tracemalloc` | stdlib | Snapshot peak/current allocations, top allocators by file:line |
| `memory_profiler` mit `@profile` | PyPI | Line-level Memory-Allocation in einer Funktion |
| `gc.get_objects()` + `Counter` | stdlib | Class-Distribution der live-objects |
| `gc.get_referrers()` walk | stdlib | Findet Holder die einen Object pinnen |
| `objgraph` | PyPI | Visualisiert reference cycles, top types growing over time |
| `pympler` | PyPI | Heap profiler with object-type-aware breakdown, leak detection |
| SIGUSR1-Handler | mhils Pattern | On-demand dump im laufenden Prozess ohne Restart |

Hätten wir EINE dieser Quellen in Phase 1 angezapft, wäre uns die O(N²)-Cumulative-Messages-Wurzel sofort sichtbar geworden statt erst nach mehreren falschen Iterationen.

## Konkrete Action-Items für nächste RAM-Investigation-Session

1. SIGUSR1-Handler in `src/panes/waste_pane.py` einbauen (30 LOC). Erst measuren WAS retained wird, dann fixen.
2. `flow.response.stream = True` in `src/proxy/addon.py` `responseheaders`-Hook ergänzen — eliminiert Body-Buffering für unsere mitmdump-Instanz (separates Problem vom pane-RAM, aber weiterer Win).
3. `gc.disable()` + manuelle `gc.collect()` in idle-Phasen testen für warnings/waste panes — ob das Render-Stutter erkennbar reduziert.
4. `memory_profiler` mit `@profile` auf `_parse_log_file`, `_scan_proxy_entries_for_errors`, `_merge_new_events` für line-level Allocation-Profil.
5. Architektonisch: glances-Pattern „User-konfigurierbarer No-History-Mode pro Pane" für die Panes wo Historie nicht zwingend ist.

Diese fünf Aktionen alle in einer Investigation-First-Session, BEVOR wieder Code-Worker dispatched werden.
