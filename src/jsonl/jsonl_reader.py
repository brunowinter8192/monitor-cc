# INFRASTRUCTURE
import json
from pathlib import Path
from typing import Iterator, List, Tuple

# FUNCTIONS

def read_json_records(path: Path, start_pos: int) -> Tuple[List[dict], int]:
    reader = JsonlReader(path, start_pos)
    records = list(reader)
    return records, reader.position

class JsonlReader:
    def __init__(self, path: Path, start_pos: int = 0):
        self.path = Path(path)
        self.position = start_pos

    def __iter__(self) -> Iterator[dict]:
        with open(self.path, 'rb') as f:
            f.seek(self.position)
            for raw in f:
                if not raw.endswith(b'\n'):
                    return
                offset = self.position
                self.position += len(raw)
                line = raw.strip()
                if not line:
                    continue
                yield _decode_line(self.path, offset, line)

def _decode_line(path: Path, offset: int, line: bytes) -> dict:
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        raise JsonlCorruptError(f'{path}: unparseable line at byte {offset}: {e}') from e

class JsonlCorruptError(ValueError):
    pass
