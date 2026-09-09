# INFRASTRUCTURE
import json
import os

# From paths.py: on-disk locations of the model-selection + proxy-rules files
from .paths import MODEL_SELECTION_FILE, PROXY_RULES_FILE

# Fixed cycle order; clicking a row button steps forward through this tuple and wraps
_MODEL_CHOICES = ("claude-opus-5", "claude-fable-5", "claude-fable-5-1", "claude-sonnet-5")
_DEFAULT_MAIN   = _MODEL_CHOICES[0]
_DEFAULT_WORKER = _MODEL_CHOICES[3]

# Fixed cycle orders for the per-model parameter rows. 'max' is deliberately excluded from
# effort — it is valid only on specific Opus models and would hard-fail requests elsewhere.
_EFFORT_CHOICES = ("low", "medium", "high")
_MAXTOK_CHOICES = (32000, 64000, 128000)
# Defaults for a model with NO model_params entry — NOT the first cycle value. A missing entry
# means the proxy injects nothing at all, and omitting effort behaves like 'high' per the API;
# 64000 is what every existing entry carries. Displaying the first cycle value (low/32000) would
# misrepresent the effective on-disk state, and an accidental Apply would silently downgrade the
# model. _next_in's unrecognized-current -> first-choice behavior is unrelated cycle mechanics
# and stays unchanged.
_DEFAULT_EFFORT     = "high"
_DEFAULT_MAX_TOKENS = 64000
_DEFAULT_THINKING   = {"type": "adaptive", "display": "summarized"}

# FUNCTIONS

# Advance current to the next value in a fixed choice tuple, wrapping; an unrecognized current
# value (e.g. a hand-edited file) starts the cycle at the first choice
def _next_in(choices: tuple, current):
    try:
        idx = choices.index(current)
    except ValueError:
        idx = -1
    return choices[(idx + 1) % len(choices)]

# Advance current model to the next value in the fixed cycle order, wrapping
def _next_model(current: str) -> str:
    return _next_in(_MODEL_CHOICES, current)

# Advance current effort to the next value in the fixed cycle order, wrapping
def _next_effort(current: str) -> str:
    return _next_in(_EFFORT_CHOICES, current)

# Advance current max_tokens to the next value in the fixed cycle order, wrapping
def _next_max_tokens(current: int) -> int:
    return _next_in(_MAXTOK_CHOICES, current)

# Read model_selection.json; returns (main, worker) verbatim as stored — an unrecognized model
# ID is preserved as-is, NOT replaced (only Apply after an actual cycle click changes a value).
# Missing/unreadable/malformed file, or an individual missing key, falls back to the default pair.
def _load_model_selection(path=MODEL_SELECTION_FILE):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("main", _DEFAULT_MAIN), d.get("worker", _DEFAULT_WORKER)
    except Exception:
        return _DEFAULT_MAIN, _DEFAULT_WORKER

# Atomic write of the model-selection pair: tempfile + os.replace, mirrors app_settings.py's
# write pattern. No try/except here — a failed Apply must not be silently swallowed; the caller
# (ModelController.handle_apply, the AppKit-safety boundary) catches and logs explicitly.
def _write_model_selection(main: str, worker: str, path=MODEL_SELECTION_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps({'main': main, 'worker': worker}), encoding='utf-8')
    os.replace(tmp, path)

# Read proxy_rules.json verbatim as a dict; missing/unreadable/malformed file falls back to {}
# (Apply then writes a fresh minimal model_params-only file — see _write_proxy_rules_model_params).
def _load_proxy_rules(path=PROXY_RULES_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

# Read (effort, max_tokens) for one model from proxy_rules.json's model_params table. Each key is
# independently defaulted (mirrors inject_helpers.py's own "each key independently optional"
# handling) — a missing file/section/entry/key all fall back the same way, to _DEFAULT_EFFORT /
# _DEFAULT_MAX_TOKENS (NOT the first cycle value — see the module-level comment on those constants).
def _load_model_params_for(model_id: str, path=PROXY_RULES_FILE) -> tuple:
    config = _load_proxy_rules(path)
    params = config.get("model_params", {}).get(model_id, {})
    return params.get("effort", _DEFAULT_EFFORT), params.get("max_tokens", _DEFAULT_MAX_TOKENS)

# Re-indent every line but the first of a json.dumps(..., indent=2) block by one extra level —
# used to splice a value serialized on its own into a line that already carries its key.
def _reindent_nested(text: str, prefix: str) -> str:
    lines = text.split('\n')
    return '\n'.join([lines[0]] + [prefix + line for line in lines[1:]])

# Render the model_params section as one compact single-line JSON object per model entry, inside
# an indent=2 object — matches the on-disk convention already established in proxy_rules.json
# (confirmed by diff: every other section is byte-identical to plain json.dumps(indent=2); only
# model_params uses this compact-per-entry style). Preserves model_params key order.
def _render_model_params(model_params: dict) -> str:
    lines = ['  "model_params": {']
    entries = list(model_params.items())
    for i, (model_id, params) in enumerate(entries):
        comma = ',' if i < len(entries) - 1 else ''
        lines.append(f'    "{model_id}": {json.dumps(params)}{comma}')
    lines.append('  }')
    return '\n'.join(lines)

# Serialize proxy_rules.json preserving its on-disk convention: standard indent=2 for every
# top-level section except model_params (rendered via _render_model_params). Round-tripping an
# untouched config through this function reproduces the original bytes exactly — the mechanism
# that keeps an Apply's diff scoped to only the two changed leaf values.
def _dumps_proxy_rules(config: dict) -> str:
    keys = list(config.keys())
    lines = ['{']
    for i, key in enumerate(keys):
        comma = ',' if i < len(keys) - 1 else ''
        if key == "model_params":
            lines.append(_render_model_params(config[key]) + comma)
        else:
            value_text = _reindent_nested(json.dumps(config[key], indent=2), '  ')
            lines.append(f'  "{key}": {value_text}{comma}')
    lines.append('}')
    return '\n'.join(lines) + '\n'

# Read-modify-write proxy_rules.json's model_params table for the two selected models: updates
# ONLY .effort/.max_tokens on each model's entry, leaving its 'thinking' block and every other
# section/key byte-identical. A missing entry is created mirroring the established shape (a
# 'thinking' block copied from that shape, plus the given effort/max_tokens). Atomic tempfile +
# os.replace, no try/except — same AppKit-safety-boundary split as _write_model_selection.
def _write_proxy_rules_model_params(main: str, main_effort: str, main_max_tokens: int,
                                     worker: str, worker_effort: str, worker_max_tokens: int,
                                     path=PROXY_RULES_FILE) -> None:
    config = _load_proxy_rules(path)
    model_params = dict(config.get("model_params", {}))
    for model_id, effort, max_tokens in (
        (main, main_effort, main_max_tokens),
        (worker, worker_effort, worker_max_tokens),
    ):
        entry = dict(model_params.get(model_id) or {"thinking": dict(_DEFAULT_THINKING)})
        entry["effort"] = effort
        entry["max_tokens"] = max_tokens
        model_params[model_id] = entry
    config = dict(config)
    config["model_params"] = model_params
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(_dumps_proxy_rules(config), encoding='utf-8')
    os.replace(tmp, path)

# Pending Models-panel selection: 6 in-memory fields, loaded from disk, advanced by cycle clicks,
# persisted by Apply. Pure state + pure I/O — no AppKit dependency, so this class lives here
# rather than in model_controller.py.
class _PendingSelection:
    def __init__(self):
        self.main = None
        self.worker = None
        self.main_effort = None
        self.main_max_tokens = None
        self.worker_effort = None
        self.worker_max_tokens = None

    # Reload all 6 fields from disk — on-disk state is authoritative only at this call.
    def load(self) -> None:
        self.main, self.worker = _load_model_selection()
        self.main_effort, self.main_max_tokens = _load_model_params_for(self.main)
        self.worker_effort, self.worker_max_tokens = _load_model_params_for(self.worker)

    # Advance main model; refreshes main effort/max_tokens to the new model's on-disk values.
    def cycle_main(self) -> None:
        self.main = _next_model(self.main)
        self.main_effort, self.main_max_tokens = _load_model_params_for(self.main)

    # Advance worker model; refreshes worker effort/max_tokens to the new model's on-disk values.
    def cycle_worker(self) -> None:
        self.worker = _next_model(self.worker)
        self.worker_effort, self.worker_max_tokens = _load_model_params_for(self.worker)

    def cycle_main_effort(self) -> None:
        self.main_effort = _next_effort(self.main_effort)

    def cycle_main_max_tokens(self) -> None:
        self.main_max_tokens = _next_max_tokens(self.main_max_tokens)

    def cycle_worker_effort(self) -> None:
        self.worker_effort = _next_effort(self.worker_effort)

    def cycle_worker_max_tokens(self) -> None:
        self.worker_max_tokens = _next_max_tokens(self.worker_max_tokens)

    # Persist the currently displayed pair + both models' effort/max_tokens. No try/except here —
    # same AppKit-safety-boundary split as the module-level write functions; the caller
    # (ModelController.handle_apply) catches and logs explicitly.
    def write(self) -> None:
        _write_model_selection(self.main, self.worker)
        _write_proxy_rules_model_params(
            self.main, self.main_effort, self.main_max_tokens,
            self.worker, self.worker_effort, self.worker_max_tokens)
