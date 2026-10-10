# INFRASTRUCTURE
import re
from collections import Counter

EMPTY_SUBSUP_RE = re.compile(r"<su[bp]>[ \t\r\n]*</su[bp]>|<su[bp]>[^<]*\?[^<]*</su[bp]>")
TORN_MATH_RES = (
    re.compile(r"_ \{"),
    re.compile(r"\^ \{"),
    re.compile(r"\\ [a-z]( [a-z])+"),
    re.compile(r"([A-Za-z] ){3,}[A-Za-z]"),
)
ENTITY_RE = re.compile(r"&(amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);")
MOJIBAKE_RE = re.compile(r"Ã.|â€")
TABLE_RE = re.compile(r"<table[ >]")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
BARE_FENCE_RE = re.compile(r"^\s*`{3,}\s*$")
SEPARATOR_CHARS = "=#-~*_.+"
SEPARATOR_SHARE = 0.7
SEPARATOR_MIN_LENGTH = 20
RUN_RE = re.compile(r"(.)\1{39,}")
MERGED_TOKEN_MIN_LENGTH = 46
MERGED_TOKEN_ALPHA_SHARE = 0.7
MERGED_TOKEN_STOP_LENGTH = 2000
OVERSIZE_LENGTH = 1000


# FUNCTIONS
def cleanup_class_counts(text: str) -> dict:
    return {
        **class_a(text),
        "B": sum(len(pattern.findall(text)) for pattern in TORN_MATH_RES),
        "C": len(ENTITY_RE.findall(text)) + len(MOJIBAKE_RE.findall(text)),
        "F": len(TABLE_RE.findall(text)),
        "G": len(IMAGE_RE.findall(text)),
        "H": count_noise(text),
        **class_i(text),
        **class_j(text),
    }


def class_a(text: str) -> dict:
    replacement = text.count("�")
    question_pairs = text.count("??")
    empty_subsup = len(EMPTY_SUBSUP_RE.findall(text))
    blank_math = sum(1 for segment in text.split("$$")[1::2] if not segment.strip())
    return {
        "A": replacement + question_pairs + empty_subsup + blank_math,
        "A_replacement_char": replacement,
    }


def count_noise(text: str) -> int:
    return count_fence_runs(text.splitlines()) + sum(1 for line in text.splitlines() if is_separator_line(line))


def count_fence_runs(lines: list[str]) -> int:
    runs = 0
    current = 0
    for line in lines + [""]:
        if BARE_FENCE_RE.match(line):
            current += 1
            continue
        if current >= 2:
            runs += 1
        current = 0
    return runs


def is_separator_line(line: str) -> bool:
    squeezed = "".join(line.split())
    if len(squeezed) < SEPARATOR_MIN_LENGTH:
        return False
    char, count = Counter(squeezed).most_common(1)[0]
    return char in SEPARATOR_CHARS and count / len(squeezed) > SEPARATOR_SHARE


def class_i(text: str) -> dict:
    flagged = [token for token in text.split() if is_merged_token(token)]
    return {
        "I": len(flagged),
        "I_over_2000": sum(1 for token in flagged if len(token) > MERGED_TOKEN_STOP_LENGTH),
    }


def is_merged_token(token: str) -> bool:
    if len(token) < MERGED_TOKEN_MIN_LENGTH:
        return False
    if "\\" in token or "http" in token or "/" in token:
        return False
    return sum(1 for ch in token if ch.isalpha()) / len(token) > MERGED_TOKEN_ALPHA_SHARE


def class_j(text: str) -> dict:
    line_lengths = [len(line) for line in text.split("\n")]
    block_lengths = [len(block.replace("\n", " ")) for block in text.split("\n\n")]
    return {
        "J_long_lines": sum(1 for length in line_lengths if length > OVERSIZE_LENGTH),
        "J_long_blocks": sum(1 for length in block_lengths if length > OVERSIZE_LENGTH),
        "J_repeat_runs": len(RUN_RE.findall(text)),
        "J_max_line": max(line_lengths, default=0),
        "J_max_block": max(block_lengths, default=0),
    }
