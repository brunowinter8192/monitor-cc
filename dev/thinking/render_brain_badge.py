# INFRASTRUCTURE
import importlib
import sys
from datetime import datetime
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_fwd_parser = importlib.import_module(f'{_ROOT_PKG}.proxy_display.forwarded_parser')
mod_render_turn = importlib.import_module(f'{_ROOT_PKG}.proxy_display.render_turn')
mod_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')
mod_utils = importlib.import_module(f'{_ROOT_PKG}.utils')

DEFAULT_LOG = WORKTREE_ROOT / 'src' / 'logs' / 'dual_log' / 'api_requests_opus_monitor_cc_1787931850_forwarded.jsonl'

# ORCHESTRATOR
def render_brain_badge_workflow(log_path: Path) -> None:
    if not log_path.exists():
        print(f"Log not found: {log_path}")
        sys.exit(1)
    entries = parse_all_entries(log_path)
    rows = render_all_headers(entries)
    write_report(log_path, rows)

# FUNCTIONS

def parse_all_entries(log_path: Path) -> list:
    entries, _pos = mod_fwd_parser._parse_forwarded_log(log_path, 0, {}, keep_last=None)
    return entries

def render_all_headers(entries: list) -> list:
    rows = []
    for idx, entry in enumerate(entries):
        model = entry.get('model', '?')
        family = 'haiku' if 'haiku' in model.lower() else ('sonnet' if 'sonnet' in model.lower() else 'opus')
        model_short = mod_format._shorten_model(model)
        label = f"#{idx} {entry.get('flow_id', '')[:8]}"
        header = mod_render_turn._build_req_header_line(
            entry, idx, label, '▶', model_short, entry.get('message_count', 0),
            '', '', 200, None,
        )
        stripped = mod_utils._ANSI_ESCAPE_RE.sub('', header)
        delta_brain = 'th' in stripped.split()
        cumulative_brain = _has_cumulative_thinking(entry)
        rows.append({
            'idx': idx, 'model': model, 'family': family, 'label': label,
            'delta_brain': delta_brain, 'cumulative_brain': cumulative_brain,
        })
    return rows

def _has_cumulative_thinking(entry: dict) -> bool:
    msgs = entry.get('messages') or []
    return any(
        any(b.get('type') == 'thinking' for b in m.get('blocks', []))
        for m in msgs if isinstance(m, dict)
    )

def write_report(log_path: Path, rows: list) -> None:
    opus_rows = [r for r in rows if r['family'] != 'haiku']
    haiku_rows = [r for r in rows if r['family'] == 'haiku']
    opus_delta_brain = sum(1 for r in opus_rows if r['delta_brain'])
    opus_cumulative_brain = sum(1 for r in opus_rows if r['cumulative_brain'])
    haiku_delta_brain = sum(1 for r in haiku_rows if r['delta_brain'])

    lines = [
        f"# Brain badge render check — {log_path.name}",
        "",
        f"Source log: `{log_path}`",
        "",
        "## Deliverable numbers (delta semantics, real render path)",
        "",
        f"- opus requests: {len(opus_rows)}",
        f"- opus requests with brain (delta): {opus_delta_brain}",
        f"- haiku requests: {len(haiku_rows)}",
        f"- haiku requests with brain (delta): {haiku_delta_brain}",
        "",
        "## Cross-check only (cumulative semantics, NOT the render path)",
        "",
        f"- opus requests with brain (cumulative, any thinking anywhere in accumulated messages): {opus_cumulative_brain}",
        "",
        "## Per-request detail",
        "",
        "| idx | family | model | label | delta brain | cumulative brain |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['idx']} | {r['family']} | {r['model']} | {r['label']} | "
            f"{'yes' if r['delta_brain'] else ''} | {'yes' if r['cumulative_brain'] else ''} |"
        )

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'render_brain_badge_{ts}.md'
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f"opus: {opus_delta_brain}/{len(opus_rows)} carry brain (delta)")
    print(f"haiku: {haiku_delta_brain}/{len(haiku_rows)} carry brain (delta)")
    print(f"cross-check - opus cumulative: {opus_cumulative_brain}/{len(opus_rows)}")
    print(f"Report written to: {report_path}")


if __name__ == '__main__':
    arg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    render_brain_badge_workflow(arg_path)
