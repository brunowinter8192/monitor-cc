# INFRASTRUCTURE
import re
import sys
from collections import namedtuple
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_WORKTREE_ROOT = _SCRIPT_DIR.parents[1]
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))

# From src/proxy/rules.py: real proxy strip pipeline — run against synthetic single-block
# messages to get ground-truth COVERED/removed-chunk decisions instead of hardcoded markers
import proxy.rules as rules
# From src/proxy/strip_vocab.py: rule-code <-> marker <-> full-name vocabulary (attribute_chunk)
import proxy.strip_vocab as strip_vocab
# From src/proxy/strip_sr.py: SR regexes + CLAUDE.md preserve-guard preamble
import proxy.strip_sr as strip_sr
# From src/proxy/message_passes.py: role=system truncation-notice marker
import proxy.message_passes as message_passes

_UUID_RE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
_HEXID_RE = re.compile(r'\b[0-9a-fA-F]{6,}\b')
_PATH_RE = re.compile(r'(?:/[\w.\-]+){2,}')
_NUM_RE = re.compile(r'\d+')
_WS_RE = re.compile(r'\s+')

# A resolved classification hit for one segment occurrence.
# kind: 'CLASS' (goes straight into the registry) | 'PENDING' (deferred two-phase user-text resolution)
ResolvedHit = namedtuple("ResolvedHit", ["kind", "ref", "label", "origin", "chars", "sample"])

# Content shapes where CC genuinely delivers top-level framing/wrappers (plain user-typed text
# or a CC-appended text block). tool_result content is OUR tool's own return value — an SR-looking
# literal inside it is quoted DATA (a fetched issue body, a `strings` dump, RAG content, source
# code containing the tag as a string), never a CC-injected wrapper, so the CLAUDE.md-preserve and
# leftover-SR extraction below must not run against tool_result content.
_TOP_LEVEL_SHAPES = ("plain_string", "text")


# FUNCTIONS

# Route a fresh segment to the right classifier by (role, section)
def _classify_segment(role, section, block_type, text, tool_name, sys_idx) -> list:
    if section == "system":
        return _classify_system_segment(sys_idx, text)
    if role == "assistant":
        return [ResolvedHit("CLASS", "OURS:assistant_text", "Assistant response text", "OURS", len(text), text)]
    if role == "system":
        return _classify_role_system_segment(text)
    if role == "user":
        return _classify_user_segment(block_type, text, tool_name)
    return [ResolvedHit("CLASS", f"UNCLASSIFIED:role_{role}", f"Message role={role} content",
                         "UNCLASSIFIED", len(text), text)]


# system[] block — sys[2]/sys[3] are unconditionally fully replaced (COVERED); sys[0]/sys[1]
# are never touched by any proxy function (verified: grep for system[0]/system[1] mutation
# across src/proxy/*.py returns nothing) -> UNCLASSIFIED.
def _classify_system_segment(idx, text) -> list:
    if idx == 2:
        return [ResolvedHit("CLASS", "COVERED:SYS2_REPLACE",
                             "sys[2] CC agent system prompt — fully replaced by proxy rules (`_apply_system_passes`)",
                             "COVERED", len(text), text)]
    if idx == 3:
        return [ResolvedHit("CLASS", "COVERED:SYS3_REPLACE",
                             "sys[3] session/environment context block — fully replaced with '.' (`_strip_sys3`)",
                             "COVERED", len(text), text)]
    if idx == 0:
        return [ResolvedHit("CLASS", "UNCLASSIFIED:SYS0", "sys[0] billing header (x-anthropic-billing-header)",
                             "UNCLASSIFIED", len(text), text)]
    if idx == 1:
        return [ResolvedHit("CLASS", "UNCLASSIFIED:SYS1", 'sys[1] "You are Claude Code..." intro line',
                             "UNCLASSIFIED", len(text), text)]
    return [ResolvedHit("CLASS", f"UNCLASSIFIED:SYS{idx}", f"sys[{idx}] block (unexpected index in this corpus)",
                         "UNCLASSIFIED", len(text), text)]


# role=system message (message-level, bare content) — RS rule (_apply_role_system_strip) wipes
# ALL role=system content unconditionally, EXCEPT the Read-tool truncation notice (KEEP, guarded
# in production by `content.startswith('[Truncated:')`).
def _classify_role_system_segment(text) -> list:
    if text.startswith(message_passes._TRUNCATION_NOTICE_MARKER):
        return [ResolvedHit("CLASS", "KEEP:read_truncation_notice",
                             "Read-tool truncation notice (role=system, preserved by RS guard)",
                             "KEEP", len(text), text)]
    payload = {"system": [], "messages": [{"role": "system", "content": text}]}
    _, mods, *_ = rules.apply_modification_rules(payload)
    if "stripped_role_system_msg" in mods:
        sig = _normalize_template(text)[:100]
        class_key = f"COVERED:RS:{sig}"
        label = f'role=system message content — RS-covered ("{sig}")'
        return [ResolvedHit("CLASS", class_key, label, "COVERED", len(text), text)]
    return [ResolvedHit("CLASS", "UNCLASSIFIED:role_system_unhandled",
                         "role=system message content that RS did not fire on (unexpected)",
                         "UNCLASSIFIED", len(text), text)]


# role=user segment — run the real proxy strip pipeline on a synthetic single-block message,
# then peel off KEEP wrappers / leftover unmatched SR blocks from the residual, then bucket
# whatever's left as OURS (tool/user content) or defer top-level text for two-phase resolution.
def _classify_user_segment(block_type, text, tool_name) -> list:
    content = _wrap_content(block_type, text)
    payload = {"system": [], "messages": [{"role": "user", "content": content}]}
    modified, mods, _orig2, _idxs, _origs, removed, injected, _ops = rules.apply_modification_rules(payload)
    residual = _unwrap_content(block_type, modified["messages"][0]["content"])
    hits, residual = _extract_covered_and_injected(removed, injected, residual)

    if "stripped_po_preview" in mods:
        hits.append(_po_wrapper_hit(residual))
        return hits  # PO block content is entirely the wrapper; nothing else to classify

    if not residual or residual.strip() in ("", "."):
        return hits

    return hits + _classify_user_residual(block_type, residual, tool_name)


def _extract_covered_and_injected(removed, injected, residual) -> tuple:
    removed_chunks = removed.get(0, []) if removed else []
    injected_chunks = injected.get(0, []) if injected else []
    hits = []
    for chunk in removed_chunks:
        if not chunk:
            continue
        code = strip_vocab.attribute_chunk(chunk) or "ALL"
        rule_name = strip_vocab.RULES.get(code, ("unattributed_strip", []))[0]
        hits.append(ResolvedHit("CLASS", f"COVERED:{code}", f"`{rule_name}` (rule {code})",
                                 "COVERED", len(chunk), chunk))

    # Text the PROXY ITSELF added (e.g. TN/BGK wake-up replacement) — ground truth is the
    # pipeline's own injected_msg_added output, same principle as removed_chunks for COVERED.
    # It round-trips back into a LATER request's history (CC persists what was actually sent,
    # not what CC intended) and would otherwise misread as a CC-authored recurring template.
    # Subtracted from residual so it isn't ALSO counted as OURS/UNCLASSIFIED below.
    for chunk in injected_chunks:
        if not chunk or chunk not in residual:
            continue
        residual = residual.replace(chunk, "", 1)
        sig = _normalize_template(chunk)[:100]
        hits.append(ResolvedHit("CLASS", f"INJECTED:{sig}", f'Proxy-injected text ("{sig}")',
                                 "INJECTED", len(chunk), chunk))
    return hits, residual


def _po_wrapper_hit(residual) -> ResolvedHit:
    wrapper_text = residual.strip()
    return ResolvedHit("CLASS", "KEEP:po_wrapper",
                        "<persisted-output> wrapper (Preview stripped by PP rule, wrapper kept)",
                        "KEEP", len(wrapper_text), wrapper_text)


def _classify_user_residual(block_type, residual, tool_name) -> list:
    hits = []
    if block_type in _TOP_LEVEL_SHAPES:
        claude_blocks, residual = _extract_claudemd_blocks(residual)
        for cb in claude_blocks:
            hits.append(ResolvedHit("CLASS", "KEEP:claudemd_context",
                                     "CLAUDE.md context block (SR, preserve-guarded in strip_sr.py)",
                                     "KEEP", len(cb), cb))

        leftover_srs, residual = _extract_leftover_sr_blocks(residual)
        for sr in leftover_srs:
            sig = _normalize_template(sr)[:100]
            hits.append(ResolvedHit("CLASS", f"UNCLASSIFIED:sr:{sig}",
                                     f'Unmatched <system-reminder> block ("{sig}")',
                                     "UNCLASSIFIED", len(sr), sr))

        if not residual or residual.strip() in ("", "."):
            return hits

    if block_type in ("tool_result_str", "tool_result_text"):
        tname = tool_name or "(unresolved tool)"
        hits.append(ResolvedHit("CLASS", f"OURS:tool_result:{tname}", f"Tool result output — {tname}",
                                 "OURS", len(residual), residual))
    else:
        sig = _normalize_template(residual)[:120]
        hits.append(ResolvedHit("PENDING", sig, None, None, len(residual), residual))

    return hits


def _wrap_content(block_type, text):
    if block_type == "plain_string":
        return text
    if block_type == "text":
        return [{"type": "text", "text": text}]
    if block_type == "tool_result_str":
        return [{"type": "tool_result", "tool_use_id": "synthetic", "content": text}]
    if block_type == "tool_result_text":
        return [{"type": "tool_result", "tool_use_id": "synthetic", "content": [{"type": "text", "text": text}]}]
    raise ValueError(f"unknown block_type {block_type}")


def _unwrap_content(block_type, content) -> str:
    if block_type == "plain_string":
        return content if isinstance(content, str) else ""
    if not isinstance(content, list) or not content:
        return ""
    blk = content[0]
    if not isinstance(blk, dict):
        return ""
    if block_type == "text":
        return blk.get("text", "")
    if block_type == "tool_result_str":
        inner = blk.get("content", "")
        return inner if isinstance(inner, str) else ""
    if block_type == "tool_result_text":
        inner = blk.get("content", [])
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0].get("text", "")
        return ""
    return ""


# Peel out CLAUDE.md-context SR blocks (strip_sr._PRESERVE_PREAMBLE guard) from residual text.
# Only called for top-level shapes (see `_TOP_LEVEL_SHAPES`) — CLAUDE.md context is delivered as
# its own top-level message block, never nested inside a tool_result's own content.
def _extract_claudemd_blocks(text: str) -> tuple:
    kept = []

    def _repl(m):
        full = m.group(0)
        inner_m = strip_sr._INNER_SR_RE.search(full)
        inner = inner_m.group(1).strip() if inner_m else ""
        if inner.startswith(strip_sr._PRESERVE_PREAMBLE):
            kept.append(full)
            return ""
        return full

    new_text = strip_sr._STANDALONE_SR_RE.sub(_repl, text)
    return kept, new_text


# Any <system-reminder> block still standing after the full pipeline matched no known template —
# a genuine gap: proxy strips nothing here, no strip_vocab entry exists for it. Only called for
# top-level shapes (see `_TOP_LEVEL_SHAPES`) — inside tool_result this would be quoted OUR data,
# not a CC wrapper.
def _extract_leftover_sr_blocks(text: str) -> tuple:
    blocks = strip_sr._STANDALONE_SR_RE.findall(text)
    if not blocks:
        return [], text
    return blocks, strip_sr._STANDALONE_SR_RE.sub("", text)


# Normalize variable data (ids/paths/numbers) to placeholders for template-signature grouping
def _normalize_template(text: str) -> str:
    t = _UUID_RE.sub("<UUID>", text)
    t = _PATH_RE.sub("<PATH>", t)
    t = _HEXID_RE.sub("<HEX>", t)
    t = _NUM_RE.sub("#", t)
    return _WS_RE.sub(" ", t).strip()
