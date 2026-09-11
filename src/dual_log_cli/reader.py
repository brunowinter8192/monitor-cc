# INFRASTRUCTURE
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..proxy.message_summary import _infer_model_family as infer_family

_MODEL_RE = re.compile(rb'"model"\s*:\s*"([^"]+)"')
_MODEL_SNIFF_BYTES = 512
_REVERSE_CHUNK_BYTES = 1 << 20

# FUNCTIONS


def local_datetime(timestamp: str):
    if not timestamp:
        return None
    try:
        aware_utc = datetime.fromisoformat(timestamp.rstrip("Z")).replace(tzinfo=timezone.utc)
        return aware_utc.astimezone()
    except ValueError:
        return None


def iter_line_offsets_reverse(path: Path, chunk_bytes: int = _REVERSE_CHUNK_BYTES):
    size = path.stat().st_size
    if size == 0:
        return
    line_end = size
    pos = size
    buf = b""
    with open(path, "rb") as fh:
        while pos > 0:
            read_len = min(chunk_bytes, pos)
            pos -= read_len
            fh.seek(pos)
            buf = fh.read(read_len) + buf
            while True:
                search_end = len(buf) - 1 if buf.endswith(b"\n") else len(buf)
                nl = buf.rfind(b"\n", 0, search_end)
                if nl == -1:
                    break
                line_start = pos + nl + 1
                if line_end > line_start:
                    yield line_start, line_end - line_start
                line_end = line_start
                buf = buf[:nl]
    if line_end > 0:
        yield 0, line_end


def sniff_model(fh, offset: int) -> str:
    fh.seek(offset)
    match = _MODEL_RE.search(fh.read(_MODEL_SNIFF_BYTES))
    return match.group(1).decode("utf-8", "replace") if match else ""


def read_json_line(path: Path, offset: int, length: int) -> dict:
    with open(path, "rb") as fh:
        fh.seek(offset)
        raw = fh.read(length)
    return json.loads(raw)


def load_last_request(original_path: Path) -> tuple:
    skipped = 0
    with open(original_path, "rb") as fh:
        for offset, length in iter_line_offsets_reverse(original_path):
            model = sniff_model(fh, offset)
            if model and infer_family(model) == "haiku":
                skipped += 1
                continue
            fh.seek(offset)
            raw = fh.read(length)
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                skipped += 1
                continue
            tools = (entry.get("payload") or {}).get("tools") or []
            if not tools:
                skipped += 1
                continue
            return entry, length, skipped
    return None, 0, skipped


def iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
