# INFRASTRUCTURE
import json

import tiktoken

# FUNCTIONS

def compute_ratios(paired: list) -> tuple:
    msg_ratios = []
    prefix_ratio = None
    prefix_info = {}

    for row in paired:
        tok = row.get("token")
        if tok is None:
            continue
        cr = tok["cr"]
        cc = tok["cc"]
        has_thinking = tok["has_thinking"]
        delta = row.get("delta_msgs_chars")
        req_n = row["req_n"]

        if req_n == 1 and not has_thinking and (cc + cr) > 0:
            total_chars = row["sys_chars"] + row["tools_chars"] + row["msgs_chars"]
            prefix_ratio = total_chars / (cc + cr)
            prefix_info = {
                "req_n": req_n,
                "total_chars": total_chars,
                "total_tokens": cc + cr,
                "cr": cr,
                "cc": cc,
            }

        if req_n >= 2 and not has_thinking and delta is not None and delta > 0 and cc > 0:
            msg_ratios.append({"ratio": delta / cc, "row": row, "tok": tok})

    return msg_ratios, prefix_ratio, prefix_info


def compute_tiktoken_drift(proxy_path, paired: list) -> list:
    enc = tiktoken.get_encoding("cl100k_base")
    drift_rows = []
    for row in paired:
        tok = row.get("token")
        if tok is None or tok["cc"] == 0:
            continue
        rp = row.get("raw_payload", {})
        parts = []
        for block in rp.get("system", []) or []:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
        for tool in rp.get("tools", []) or []:
            parts.append(json.dumps(tool, ensure_ascii=False))
        for msg in rp.get("messages", []) or []:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict):
                        parts.append(b.get("text", ""))
        full_text = "\n".join(parts)
        tiktoken_est = len(enc.encode(full_text))
        actual_total = tok["cr"] + tok["cc"] + tok["d"]
        drift_pct = (tiktoken_est - actual_total) / actual_total * 100 if actual_total > 0 else 0.0
        drift_rows.append({
            "req_n": row["req_n"],
            "tiktoken_est": tiktoken_est,
            "actual_total": actual_total,
            "cr": tok["cr"],
            "cc": tok["cc"],
            "d": tok["d"],
            "drift_pct": drift_pct,
            "has_thinking": tok["has_thinking"],
        })
    return drift_rows
