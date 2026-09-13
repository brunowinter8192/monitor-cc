# INFRASTRUCTURE
import re

_MODEL_PROBE_BYTE_BUDGET = 8192
_MESSAGE_START_MODEL_RE = re.compile(
    rb'"type":\s*"message_start".*?"model":\s*"([^"]+)"', re.DOTALL
)

# FUNCTIONS


def make_answering_model_probe() -> tuple:
    state = {"model": "", "done": False}
    buffer = bytearray()

    def probe(chunk: bytes) -> bytes:
        if state["done"] or not chunk:
            return chunk
        buffer.extend(chunk)
        match = _MESSAGE_START_MODEL_RE.search(bytes(buffer))
        if match:
            state["model"] = match.group(1).decode("utf-8", "replace")
            state["done"] = True
        elif len(buffer) >= _MODEL_PROBE_BYTE_BUDGET:
            state["done"] = True
        return chunk

    return probe, state
