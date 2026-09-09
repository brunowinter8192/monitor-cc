# INFRASTRUCTURE
import json

# FUNCTIONS

def _serialize_workers(key, worker_turns: dict) -> str:
    if isinstance(key, tuple):
        w_name, t_idx, c_idx = key
        turns = worker_turns.get(w_name, [])
        if t_idx >= len(turns):
            return ''
        turn = turns[t_idx]
        calls = turn.get('api_calls', [])
        if c_idx >= len(calls):
            return ''
        call = calls[c_idx]
        parts = [f"Worker: {w_name}  Turn {t_idx + 1}, Call {c_idx + 1}  CR:{call.get('cache_read', 0)}  CC:{call.get('cache_creation', 0)}  D:{call.get('direct', 0)}  out:{call.get('output_tokens', 0)}"]
        for blk in call.get('content_blocks', []):
            btype = blk.get('type', '')
            if btype == 'tool_use':
                tool_name = blk.get('tool_name', 'Unknown')
                inp = blk.get('preview', {})
                parts.append(f"\n--- tool_use: {tool_name} ---")
                parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
            elif btype == 'text':
                parts.append(f"\n--- text ---")
                parts.append(blk.get('preview', ''))
        return '\n'.join(parts)
    else:
        name = str(key)
        turns = worker_turns.get(name, [])
        n_turns = len(turns)
        n_calls = sum(len(t.get('api_calls', [])) for t in turns)
        return f"Worker: {name}\nTurns: {n_turns}  API calls: {n_calls}"
