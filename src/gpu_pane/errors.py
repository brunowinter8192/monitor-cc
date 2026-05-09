# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path

RAG_LOG_DIR = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/src/rag/logs")
ERRORS_FILE = RAG_LOG_DIR / "errors.jsonl"

# FUNCTIONS

# Return all entries from errors.jsonl whose ts >= local midnight; [] if file missing
def errors_today() -> list[dict]:
    now_local = datetime.now().astimezone()
    today_start = (now_local
                   .replace(hour=0, minute=0, second=0, microsecond=0)
                   .astimezone(timezone.utc))
    return [e for e in _read_all() if datetime.fromisoformat(e["ts"]) >= today_start]


# Return per-server count of today's errors
def errors_today_by_server() -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in errors_today():
        srv = e.get("server", "unknown")
        counts[srv] = counts.get(srv, 0) + 1
    return counts


# Read all JSON lines from ERRORS_FILE; [] on FileNotFoundError or empty
def _read_all() -> list[dict]:
    try:
        lines = ERRORS_FILE.read_text().splitlines()
    except FileNotFoundError:
        return []
    result = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return result
