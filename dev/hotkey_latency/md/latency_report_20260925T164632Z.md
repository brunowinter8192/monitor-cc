# Hotkey/Menubar Latency Report

Source: `/tmp/menubar_0925.log`
Generated: 2026-09-25T16:46:32+00:00

## Main-Thread Tick Latency (over-threshold ticks only)

Total-duration distribution: n=71 mean=471.3 median=339.0 p90=693.0 p95=1223.0 max=3041.0

### Per-Phase Distribution (ms)

- `launch_tick`: n=71 mean=0.0 median=0.0 p90=0.0 p95=0.0 max=2.0
- `panel_rebuild_update`: n=71 mean=401.3 median=280.0 p90=675.0 p95=1223.0 max=3041.0
- `rag_tick`: n=71 mean=55.1 median=0.0 p90=226.0 p95=335.0 max=468.0
- `snapshot_consume`: n=71 mean=10.6 median=0.0 p90=0.0 p95=3.0 max=510.0

### Slowest 10 Entries

- 2026-09-25T12:17:28 total=3041ms — panel_rebuild_update=3041ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T15:37:35 total=1914ms — panel_rebuild_update=1910ms rag_tick=5ms snapshot_consume=0ms launch_tick=0ms
- 2026-09-25T12:46:05 total=1625ms — panel_rebuild_update=1625ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T00:17:21 total=1433ms — panel_rebuild_update=1433ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T14:11:38 total=1223ms — panel_rebuild_update=1223ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T00:08:51 total=1131ms — panel_rebuild_update=637ms rag_tick=468ms snapshot_consume=0ms launch_tick=0ms
- 2026-09-25T13:52:52 total=862ms — panel_rebuild_update=813ms snapshot_consume=49ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T12:18:21 total=693ms — panel_rebuild_update=693ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T00:08:01 total=675ms — panel_rebuild_update=675ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms
- 2026-09-25T12:16:33 total=631ms — panel_rebuild_update=631ms snapshot_consume=0ms rag_tick=0ms launch_tick=0ms

## Background Discovery-Worker Cycle Latency (over-threshold cycles only)

Total-duration distribution: n=6380 mean=2634.7 median=3217.5 p90=3436.0 p95=3524.0 max=25780.0

### Per-Phase Distribution (ms)

- `bg_task_lsof`: n=6380 mean=115.7 median=113.0 p90=131.0 p95=153.0 max=3906.0
- `desktop_detection`: n=6380 mean=1934.8 median=2404.0 p90=2772.0 p95=2797.0 max=9789.0
- `ghostty`: n=6380 mean=189.2 median=193.0 p90=295.0 p95=343.0 max=4118.0
- `per_project_loop`: n=6380 mean=100.2 median=23.0 p90=118.0 p95=179.0 max=14074.0
- `proc_cache`: n=6380 mean=192.6 median=186.0 p90=286.0 p95=328.0 max=4436.0
- `tmux_state`: n=6380 mean=11.0 median=0.0 p90=9.0 p95=18.0 max=3402.0

### Slowest 10 Entries

- 2026-09-25T12:17:49 total=25780ms — per_project_loop=12575ms ghostty=2883ms tmux_state=1987ms proc_cache=0ms bg_task_lsof=0ms desktop_detection=0ms
- 2026-09-25T00:17:41 total=22440ms — desktop_detection=6278ms bg_task_lsof=3906ms proc_cache=3179ms ghostty=2417ms per_project_loop=1000ms tmux_state=821ms
- 2026-09-25T10:44:56 total=18660ms — desktop_detection=6770ms ghostty=3530ms bg_task_lsof=3134ms proc_cache=2853ms per_project_loop=855ms tmux_state=93ms
- 2026-09-25T15:38:03 total=18639ms — per_project_loop=4895ms desktop_detection=4464ms bg_task_lsof=3359ms proc_cache=3345ms ghostty=2162ms tmux_state=342ms
- 2026-09-25T12:46:20 total=18469ms — desktop_detection=6430ms proc_cache=3908ms bg_task_lsof=3428ms ghostty=2387ms per_project_loop=867ms tmux_state=641ms
- 2026-09-25T10:47:03 total=18170ms — desktop_detection=6866ms ghostty=4118ms proc_cache=3119ms bg_task_lsof=3056ms per_project_loop=676ms tmux_state=270ms
- 2026-09-25T12:16:32 total=17611ms — desktop_detection=9789ms proc_cache=338ms bg_task_lsof=299ms ghostty=242ms per_project_loop=116ms tmux_state=0ms
- 2026-09-25T13:52:51 total=16026ms — per_project_loop=8483ms proc_cache=0ms ghostty=0ms tmux_state=0ms bg_task_lsof=0ms desktop_detection=0ms
- 2026-09-25T14:11:52 total=15756ms — bg_task_lsof=3790ms proc_cache=3225ms desktop_detection=2965ms ghostty=2781ms per_project_loop=1930ms tmux_state=1000ms
- 2026-09-25T14:12:41 total=14373ms — bg_task_lsof=3499ms ghostty=3141ms desktop_detection=2455ms per_project_loop=1897ms proc_cache=195ms tmux_state=0ms

## Hotkey Queue-Delay (queue_delay_ms = handler-entry time - Carbon event timestamp)

Overall: n=424 mean=10.4 median=0.2 p90=0.4 p95=1.0 max=2394.8

### Per Hotkey

- `cmd+1`: n=14 mean=0.2 median=0.2 p90=0.2 p95=0.2 max=0.4
- `cmd+2`: n=41 mean=17.0 median=0.1 p90=84.5 p95=141.1 max=214.4
- `cmd+3`: n=17 mean=0.1 median=0.1 p90=0.2 p95=0.2 max=0.2
- `cmd+k`: n=327 mean=10.3 median=0.2 p90=0.4 p95=0.6 max=2394.8
- `cmd+l`: n=20 mean=18.6 median=0.2 p90=103.9 p95=127.0 max=134.4
- `cmd+left`: n=2 mean=0.2 median=0.2 p90=0.3 p95=0.3 max=0.3
- `cmd+right`: n=3 mean=0.1 median=0.1 p90=0.1 p95=0.1 max=0.1

## Focus-Path Timing (_focus_session)

- `lookup_ms` (get_ghostty_terminal_id): n=96 mean=0.0 median=0.0 p90=0.0 p95=0.1 max=0.1
- `osascript_ms` (osascript run): n=96 mean=187.3 median=111.4 p90=139.3 p95=147.4 max=3535.2
