# INFRASTRUCTURE
import subprocess
import time

TOGGLE_TIMEOUT = 120   # seconds before [starting…]/[stopping…] label expires

_toggle_state: dict = {}   # preset name or 'port-{N}' → ('starting'|'stopping', float ts)

# FUNCTIONS

# Remove _toggle_state entries when action completed or timed out
def _expire_toggle_states(presets: list, arbitrary: list) -> None:
    now = time.time()
    for key in list(_toggle_state.keys()):
        action, ts = _toggle_state[key]
        if now - ts > TOGGLE_TIMEOUT:
            del _toggle_state[key]
            continue
        if key.startswith('port-'):
            try:
                port_n = int(key[5:])
            except ValueError:
                continue
            s = next((x for x in arbitrary if x['port'] == port_n), None)
        else:
            s = next((x for x in presets if x['name'] == key), None)
        if s is None:
            continue
        if action == 'starting' and s['running'] and s['healthy']:
            del _toggle_state[key]
        elif action == 'stopping' and not s['running']:
            del _toggle_state[key]


# Fire-and-forget action via rag-cli; target is preset name or 'port-{N}' for arbitrary
def _fire_button(action: str, target: str) -> None:
    devnull = subprocess.DEVNULL
    if target.startswith('port-'):
        port = target[5:]
        subprocess.Popen(["rag-cli", "server", "stop", "--port", port],
                         stdout=devnull, stderr=devnull)
    else:
        subprocess.Popen(["rag-cli", "server", action, target],
                         stdout=devnull, stderr=devnull)
    _toggle_state[target] = ('starting' if action in ('start', 'restart') else 'stopping',
                              time.time())
