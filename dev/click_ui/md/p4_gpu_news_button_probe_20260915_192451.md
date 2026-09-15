# P4 -- gpu + news pane button probe run (2026-09-15T19:24:51.843082+00:00)

**Result: 53/53 checks passed**

| Check | Result |
|---|---|
| gpu: both preset rows have a button region | PASS |
| gpu: preset button rows are disjoint from the [refresh] header row | PASS |
| gpu: registered button action for 'preset-a' is 'start' | PASS |
| gpu: click on 'preset-a' button dispatched (matched region, fired) | PASS |
| gpu: click/digit-key parity for 'preset-a' -- same subprocess.Popen args | PASS |
| gpu: click/digit-key parity for 'preset-a' -- same _toggle_state action label (timestamps differ by real elapsed time between the two calls, not compared) | PASS |
| gpu: registered button action for 'preset-b' is 'stop' | PASS |
| gpu: click on 'preset-b' button dispatched (matched region, fired) | PASS |
| gpu: click/digit-key parity for 'preset-b' -- same subprocess.Popen args | PASS |
| gpu: click/digit-key parity for 'preset-b' -- same _toggle_state action label (timestamps differ by real elapsed time between the two calls, not compared) | PASS |
| gpu: [refresh] button region registered | PASS |
| gpu: [refresh] button on row 1 | PASS |
| gpu: [refresh] button text visible in header line | PASS |
| gpu: click on [refresh] is recognized as the refresh action (same as 'r' key branch) | PASS |
| gpu: width guard -- no [refresh] region when pane_width=20 (too narrow) | PASS |
| gpu: width guard -- no [refresh] text in header when too narrow | PASS |
| gpu width=5: no [refresh] region (too narrow even at the rule minimum) | PASS |
| gpu width=5: title text 'GPU Servers' still fully visible | PASS |
| gpu width=20: no [refresh] region (too narrow even at the rule minimum) | PASS |
| gpu width=20: title text 'GPU Servers' still fully visible | PASS |
| gpu width=26: no [refresh] region (too narrow even at the rule minimum) | PASS |
| gpu width=26: title text 'GPU Servers' still fully visible | PASS |
| gpu width=27: [refresh] region registered (decoration yielded, not the button) | PASS |
| gpu width=27: rule shrank below its 64-char cap to make room | PASS |
| gpu width=30: [refresh] region registered (decoration yielded, not the button) | PASS |
| gpu width=30: rule shrank below its 64-char cap to make room | PASS |
| gpu width=50: [refresh] region registered (decoration yielded, not the button) | PASS |
| gpu width=50: rule shrank below its 64-char cap to make room | PASS |
| gpu width=90: [refresh] region registered (decoration yielded, not the button) | PASS |
| gpu width=130: [refresh] region registered (decoration yielded, not the button) | PASS |
| gpu width=215: [refresh] region registered (decoration yielded, not the button) | PASS |
| news: [refresh] button region registered | PASS |
| news: [run pipeline] button region still registered (unchanged) | PASS |
| news: [refresh] and [run pipeline] rows are disjoint (no collision) | PASS |
| news: [refresh] button text visible in header line | PASS |
| news: click on [refresh] is recognized as the refresh action (same as 'r' key branch) | PASS |
| news: [run pipeline] click still fires the pipeline (regression) | PASS |
| news: width guard -- no [refresh] region when pane_width=15 (too narrow) | PASS |
| news: width guard -- no [refresh] text in header when too narrow | PASS |
| news width=5: no [refresh] region (too narrow even at the rule minimum) | PASS |
| news width=5: title text 'CoinDesk News Pipeline' still fully visible | PASS |
| news width=20: no [refresh] region (too narrow even at the rule minimum) | PASS |
| news width=20: title text 'CoinDesk News Pipeline' still fully visible | PASS |
| news width=37: no [refresh] region (too narrow even at the rule minimum) | PASS |
| news width=37: title text 'CoinDesk News Pipeline' still fully visible | PASS |
| news width=38: [refresh] region registered (decoration yielded, not the button) | PASS |
| news width=38: rule shrank below its 52-char cap to make room | PASS |
| news width=40: [refresh] region registered (decoration yielded, not the button) | PASS |
| news width=40: rule shrank below its 52-char cap to make room | PASS |
| news width=60: [refresh] region registered (decoration yielded, not the button) | PASS |
| news width=60: rule shrank below its 52-char cap to make room | PASS |
| news width=86: [refresh] region registered (decoration yielded, not the button) | PASS |
| news width=107: [refresh] region registered (decoration yielded, not the button) | PASS |
