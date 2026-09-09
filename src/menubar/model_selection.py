# INFRASTRUCTURE
import json
import os

from .paths import MODEL_SELECTION_FILE, PROXY_RULES_FILE

_MODEL_CHOICES = ("claude-opus-5", "claude-fable-5", "claude-fable-5-1", "claude-sonnet-5")
_DEFAULT_MAIN   = _MODEL_CHOICES[0]
_DEFAULT_WORKER = _MODEL_CHOICES[3]

_EFFORT_CHOICES = ("low", "medium", "high")
_MAXTOK_CHOICES = (32000, 64000, 128000)
_DEFAULT_EFFORT     = "high"
_DEFAULT_MAX_TOKENS = 64000
_DEFAULT_THINKING   = {"type": "adaptive", "display": "summarized"}

# FUNCTIONS

def _next_in(choices: tuple, current):
    try:
        idx = choices.index(current)
    except ValueError:
        idx = -1
    return choices[(idx + 1) % len(choices)]

def _next_model(current: str) -> str:
    return _next_in(_MODEL_CHOICES, current)

def _next_effort(current: str) -> str:
    return _next_in(_EFFORT_CHOICES, current)

def _next_max_tokens(current: int) -> int:
    return _next_in(_MAXTOK_CHOICES, current)

def _load_model_selection(path=MODEL_SELECTION_FILE):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("main", _DEFAULT_MAIN), d.get("worker", _DEFAULT_WORKER)
    except Exception:
        return _DEFAULT_MAIN, _DEFAULT_WORKER

def _write_model_selection(main: str, worker: str, path=MODEL_SELECTION_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps({'main': main, 'worker': worker}), encoding='utf-8')
    os.replace(tmp, path)

def _load_proxy_rules(path=PROXY_RULES_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _load_model_params_for(model_id: str, path=PROXY_RULES_FILE) -> tuple:
    config = _load_proxy_rules(path)
    params = config.get("model_params", {}).get(model_id, {})
    return params.get("effort", _DEFAULT_EFFORT), params.get("max_tokens", _DEFAULT_MAX_TOKENS)

def _reindent_nested(text: str, prefix: str) -> str:
    lines = text.split('\n')
    return '\n'.join([lines[0]] + [prefix + line for line in lines[1:]])

def _render_model_params(model_params: dict) -> str:
    lines = ['  "model_params": {']
    entries = list(model_params.items())
    for i, (model_id, params) in enumerate(entries):
        comma = ',' if i < len(entries) - 1 else ''
        lines.append(f'    "{model_id}": {json.dumps(params)}{comma}')
    lines.append('  }')
    return '\n'.join(lines)

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

class _PendingSelection:
    def __init__(self):
        self.main = None
        self.worker = None
        self.main_effort = None
        self.main_max_tokens = None
        self.worker_effort = None
        self.worker_max_tokens = None

    def load(self) -> None:
        self.main, self.worker = _load_model_selection()
        self.main_effort, self.main_max_tokens = _load_model_params_for(self.main)
        self.worker_effort, self.worker_max_tokens = _load_model_params_for(self.worker)

    def cycle_main(self) -> None:
        self.main = _next_model(self.main)
        self.main_effort, self.main_max_tokens = _load_model_params_for(self.main)

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

    def write(self) -> None:
        _write_model_selection(self.main, self.worker)
        _write_proxy_rules_model_params(
            self.main, self.main_effort, self.main_max_tokens,
            self.worker, self.worker_effort, self.worker_max_tokens)
