# INFRASTRUCTURE
import json
import os

from ..proxy_display.parser import proxy_session_id_for_project


# FUNCTIONS

# Append new tool error events to tool_errors.jsonl. Fail-silent on any exception.
def append_tool_errors(new_errors: list, project_filter: str = '') -> None:
    if not new_errors:
        return
    try:
        log_path = os.environ.get(
            "MONITOR_CC_TOOL_ERROR_LOG",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'src', 'logs', 'tool_errors.jsonl',
            ),
        )
        session_id = proxy_session_id_for_project(project_filter) if project_filter else ''
        with open(log_path, 'a', encoding='utf-8') as f:
            for err in new_errors:
                worker_name = err.get('worker_name', '')
                record = {
                    'ts': err.get('_ts_raw', '') or err.get('timestamp', ''),
                    'session_id': session_id,
                    'worker': f'worker:{worker_name}' if worker_name else 'main',
                    'tool_name': err.get('tool_name', ''),
                    'tool_use_id': err.get('_tool_use_id', ''),
                    'error_full': err.get('full_text', ''),
                    'proxy_file': err.get('_proxy_file', ''),
                    'request_id': err.get('_request_id', ''),
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        return
