# INFRASTRUCTURE
import sys
from datetime import datetime

from .bg_timer import _abort_bg_sleep_timers
from .menubar_log import log_menubar
from .proc_cache import _read_orchestrator_signals, ORCHESTRATOR_SIGNAL_BUFFER_SECS
from .system import _focus_session

# FUNCTIONS

# Append one line to menubar.log ([abort] category); always-on (no env-var gate)
def _abort_log_write(line: str) -> None:
    try:
        log_menubar('abort', line.rstrip('\n'))
    except Exception as e:
        print(f'[abort-log] write error: {e}', file=sys.stderr)

# True if worker-cli has signalled a send to this worker's tmux session in the last buffer window.
# Uses worker.tmux_session_name (carries the iterative-dev tmux convention basename(project_path));
# NEVER reconstruct from project_name — that's a different decoded-path heuristic (MCP-RAG vs RAG).
def _has_recent_send_signal(worker, signals: dict, now: float) -> bool:
    if not worker.tmux_session_name:
        return False
    ts = signals.get(worker.tmux_session_name)
    return ts is not None and (now - ts) < ORCHESTRATOR_SIGNAL_BUFFER_SECS

# Per-concern controller for auto-focus debounce and auto-abort idle-workers logic (Step 5/6)
class FocusController:
    def __init__(self, app) -> None:
        self.app = app
        self._idle_since_ts: dict = {}
        self._all_workers_idle_since_ts: dict = {}
        self._last_statuses: dict = {}

    # Auto-focus + auto-abort: called once per _tick after bg_by_project is computed.
    # self._last_statuses holds the OLD snapshot — update_statuses() is called at tick-end.
    # Per-project auto-abort fires when all workers of a project are idle for >=5s while a
    # bg timer is running. A worker is 'working' when hook status is working OR worker-cli
    # wrote an orchestrator signal within ORCHESTRATOR_SIGNAL_BUFFER_SECS.
    # See decisions/OldThemes/menubar_signal_grace/initial_design.md.
    def tick(self, sessions, bg_by_project: dict, now: float) -> None:
        # Auto-focus: debounce idle main sessions (working→idle transition + 3s hold-off)
        if self.app._auto_focus:
            for s in sessions:
                if s.is_worker or not s.cwd:
                    self._idle_since_ts.pop(s.name, None)
                    continue
                if s.status == 'idle' and not s.has_bg:
                    if s.name not in self._idle_since_ts:
                        if self._last_statuses.get(s.name) == 'working':
                            self._idle_since_ts[s.name] = now
                    elif now - self._idle_since_ts[s.name] >= 3.0:
                        _focus_session(s.cwd)
                        del self._idle_since_ts[s.name]
                else:
                    self._idle_since_ts.pop(s.name, None)
        # Auto-abort: fire when all workers idle for >=5s with a bg timer present
        signals = _read_orchestrator_signals(now)
        workers_by_project: dict = {}
        for s in sessions:
            if s.is_worker:
                workers_by_project.setdefault(s.project_name, []).append(s)
        for proj, proj_bg in bg_by_project.items():
            if proj == 'unknown':
                continue
            workers = workers_by_project.get(proj, [])
            all_idle = bool(workers) and all(
                w.status == 'idle' and not _has_recent_send_signal(w, signals, now)
                for w in workers
            )
            # Build log fields before mutating _all_workers_idle_since_ts
            since_idle_ts = self._all_workers_idle_since_ts.get(proj)
            since_idle_str = f'{now - since_idle_ts:.1f}' if (all_idle and since_idle_ts is not None) else '-'
            worker_tokens = []
            for w in workers:
                sig_ts = signals.get(w.tmux_session_name) if w.tmux_session_name else None
                sig_part = f'sig_age={now - sig_ts:.1f}' if sig_ts is not None else 'sig=none'
                worker_tokens.append(f'{w.name}:{w.status}:{sig_part}')
            will_abort = (all_idle and since_idle_ts is not None and (now - since_idle_ts) >= 5.0)
            ts_str = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:23]
            _abort_log_write(
                f'{ts_str} abort_check project={proj} '
                f'bg_pids=[{",".join(str(p) for p in proj_bg.sleep_pids)}] '
                f'workers=[{",".join(worker_tokens)}] '
                f'all_idle={all_idle} since_idle={since_idle_str} '
                f'decision={"ABORT" if will_abort else "hold"}\n'
            )
            if all_idle:
                if proj not in self._all_workers_idle_since_ts:
                    self._all_workers_idle_since_ts[proj] = now
                elif now - self._all_workers_idle_since_ts[proj] >= 5.0:
                    _abort_bg_sleep_timers(proj_bg.sleep_pids)
                    self._all_workers_idle_since_ts.pop(proj, None)
            else:
                self._all_workers_idle_since_ts.pop(proj, None)
        for proj in list(self._all_workers_idle_since_ts):
            if proj not in bg_by_project:
                del self._all_workers_idle_since_ts[proj]

    # True if any session status differs from _last_statuses snapshot. Does NOT update snapshot.
    # Must be called BEFORE update_statuses() within the same tick.
    def statuses_changed(self, sessions) -> bool:
        current = {s.name: s.status for s in sessions}
        return current != self._last_statuses

    # Snapshot {name: status} into _last_statuses for next-tick comparison.
    # Called at tick-end (after all status reads for the current tick are complete).
    def update_statuses(self, sessions) -> None:
        self._last_statuses = {s.name: s.status for s in sessions}
