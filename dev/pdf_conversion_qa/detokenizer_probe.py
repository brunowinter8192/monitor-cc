# INFRASTRUCTURE
import json

from mlx_vlm.tokenizer_utils import BPEStreamingDetokenizer

SPACE_BYTE = 0x20
LABEL_BYTES = {"a": 0x61, "E2": 0xE2, "80": 0x80, "9D": 0x9D}
SEQUENCES = {
    "split_right_quote_then_space_token": ["E2", "80", "SPACE_B"],
    "stray_continuation_byte": ["a", "9D", "SPACE_B"],
}


class FakeTokenizer:
    def __init__(self, vocab):
        self.vocab = vocab


# ORCHESTRATOR
def detokenizer_probe_workflow() -> None:
    BPEStreamingDetokenizer.make_byte_decoder()
    texts_by_label = build_label_texts()
    ids_by_text = {text: index for index, text in enumerate(texts_by_label.values())}
    results = {name: run_sequence(ids_by_text, texts_by_label, labels) for name, labels in SEQUENCES.items()}
    print(json.dumps(results))


# FUNCTIONS
def byte_to_char(value: int) -> str:
    for char, byte in BPEStreamingDetokenizer._byte_decoder.items():
        if byte == value:
            return char
    raise KeyError(value)


def build_label_texts() -> dict:
    texts = {label: byte_to_char(value) for label, value in LABEL_BYTES.items()}
    texts["SPACE_B"] = byte_to_char(SPACE_BYTE) + "b"
    return texts


def run_sequence(ids_by_text: dict, texts_by_label: dict, labels: list[str]) -> dict:
    detokenizer = BPEStreamingDetokenizer(FakeTokenizer(ids_by_text))
    try:
        for label in labels:
            detokenizer.add_token(ids_by_text[texts_by_label[label]])
        detokenizer.finalize()
    except UnicodeDecodeError as exc:
        return {"outcome": "UnicodeDecodeError", "detail": str(exc)}
    return {"outcome": "ok", "text": detokenizer.text}


if __name__ == "__main__":
    detokenizer_probe_workflow()
