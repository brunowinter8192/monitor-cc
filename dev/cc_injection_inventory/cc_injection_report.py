# INFRASTRUCTURE
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

_ORIGIN_ORDER = ("UNCLASSIFIED", "KEEP", "COVERED", "INJECTED", "OURS")


# FUNCTIONS

def _truncate(s: str, n: int = 160) -> str:
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…"


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def _build_report(registry: dict, file_stats: list, counters: dict, log_files: list,
                   excluded_files: list) -> str:
    lines = _build_report_header()
    lines += _build_strip_candidates_section(registry)
    lines += _build_methodology_section()
    lines += _build_corpus_section(file_stats, counters, excluded_files)
    lines += _build_summary_section(registry)
    lines += _build_origin_sections(registry)
    return "\n".join(lines) + "\n"


def _build_report_header() -> list:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        f"# CC Injection Inventory — {ts}",
        "",
        "Complete inventory of every distinguishable text class present in the raw request",
        "payloads Claude Code sends, as captured in `src/logs/dual_log/*_original.jsonl`. Every",
        "class found is listed regardless of frequency or size — this is an inventory, not a",
        "top-N ranking.",
        "",
    ]


def _build_strip_candidates_section(registry: dict) -> list:
    unclassified_rows = sorted(
        ((k, r) for k, r in registry.items() if r["origin"] == "UNCLASSIFIED"),
        key=lambda kr: -kr[1]["chars"],
    )
    lines = [
        "## Strip Candidates — CC-authored text no rule touches",
        "",
        'Direct answer to "what do we NOT strip today that should be stripped?" — every',
        "`UNCLASSIFIED` class (CC-authored, no existing rule fires on it, not previously",
        "audited/preserved), sorted by cumulative char cost. Same rows as the full `UNCLASSIFIED`",
        "table further down (role/section/block type/sample there) — nothing here is filtered out",
        "of the detailed tables below.",
        "",
        "| Class | Distinct occ. | Cum. chars |",
        "|---|---|---|",
    ]
    if unclassified_rows:
        for _key, r in unclassified_rows:
            lines.append(f"| {_md_escape(r['label'])} | {r['count']:,} | {r['chars']:,} |")
    else:
        lines.append("| *(none — every CC-authored class is already ruled on)* | — | — |")
    return lines


def _build_methodology_section() -> list:
    lines = ["", "## Methodology", ""]
    lines += _build_methodology_dedup_and_scope()
    lines += _build_methodology_origin_rules()
    lines += _build_methodology_grouping_and_scan()
    return lines


def _build_methodology_dedup_and_scope() -> list:
    return [
        "**Dedup metric.** Payloads are cumulative snapshots (each request re-sends the full",
        "conversation history), so a naive per-request scan overcounts by ~50x. Dedup key:",
        "`(file, role, section, block_type, exact segment text)` — a refinement of the prior",
        "codebase convention `(file, exact full message content)`, applied at SEGMENT granularity",
        "(one text/tool_result block, not the whole message) so a message that combines one",
        "repeated block with one genuinely new block correctly counts only the new block as a new",
        "distinct occurrence. A repeat (same file, same exact segment text) contributes to",
        "**cumulative char cost** (it is re-sent and re-billed every request) but not to",
        "**distinct occurrences** (it is the same real event, not a new one).",
        "",
        "**Segmentation.** Walks `system[0..3]` blocks, and every message's `content` — plain",
        "string, `text` blocks, and `tool_result` blocks (`.content` string or list of `{type:",
        "text}` sub-blocks). Does not descend into `tool_use.input`, `image`, or `document`",
        "blocks. `tool_result` segments are attributed to the originating tool by resolving",
        "`tool_use_id` against the preceding assistant `tool_use` block in the same payload.",
        "",
    ]


def _build_methodology_origin_rules() -> list:
    return [
        "**Origin classification — 5 labels.** For every `role=user` and `role=system` segment, a",
        "synthetic single-block message is built matching the segment's real content shape and run",
        "through the REAL production pipeline (`src/proxy/rules.py:apply_modification_rules`) — no",
        "hardcoded marker lists. Chunks the pipeline actually REMOVES are attributed to a rule code",
        "via `strip_vocab.attribute_chunk` -> `COVERED`. Chunks the pipeline actually ADDS (the",
        "`injected_msg_added` return value — same ground-truth principle as removed-chunks for",
        "COVERED) -> `INJECTED`: text the PROXY ITSELF wrote, e.g. `strip_bg_completed.py`'s",
        "`_WAKEUP_TEXT` replacing a `<task-notification>`/background-exit block. This text then",
        "round-trips back into a LATER request's history — CC persists what was actually sent over",
        "the wire, not what CC intended — so without this label it would misread as a CC-authored",
        "recurring template. The 3 known preserve-guarded cases (Read-tool truncation notice,",
        "`<persisted-output>` wrapper, CLAUDE.md context SR) are detected explicitly on the",
        "pipeline's residual output -> `KEEP`. `role=assistant` text is never touched by any pass",
        "(verified: no `_apply_*` pass in `rules.py` gates on `role=='assistant'`) -> `OURS`",
        "directly.",
        "",
        "**tool_result vs top-level text — the enclosing shape decides, not the bytes.**",
        "`tool_result.content` is OUR tool's own return value (bash/git/file output, retrieved",
        "documents) — a `<system-reminder>` or CLAUDE.md-preamble literal appearing INSIDE it is",
        "quoted DATA (a fetched issue body, a `strings` dump of the CC binary, source containing the",
        "tag as a string), never a CC-injected wrapper, so the CLAUDE.md-preserve and leftover-SR",
        "extraction passes only run on top-level shapes (`plain_string` / `text` blocks) — any such",
        "literal inside `tool_result` content stays part of that segment's `OURS` residual, bucketed",
        "by tool name like the rest of the tool's output. On a top-level shape, a leftover unmatched",
        "`<system-reminder>` block after the full pipeline IS a genuine gap (no strip_vocab entry",
        "exists for it) -> `UNCLASSIFIED`. Remaining `tool_result` residual (not otherwise KEEP/",
        "COVERED) is `OURS`, bucketed by tool name.",
        "",
        "Remaining top-level user text uses a two-phase signature check: a normalized-text",
        "signature (>=40 chars) needs >=2 SUBSTANTIVELY DISTINCT underlying variants to count as a",
        "recurring CC template -> `UNCLASSIFIED`. Distinctness collapses two kinds of false",
        "recurrence: (a) whitespace-only differences (a trailing-newline shape artifact observed",
        "mid-corpus), and (b) containment — one variant being a verbatim substring (prefix, suffix,",
        "or mid-string extension) of another, which is one human message edited/resent as it grew,",
        "not two occurrences of a template. Short recurring text (greetings/acks like \"done\",",
        "\"ok\"), whitespace/containment-collapsed pairs, and all singletons fold into one `OURS`",
        "aggregate (genuinely unique or naturally-repeated human prose). `system[2]`/",
        "`system[3]` are unconditionally fully replaced by the proxy (`_apply_system_passes` /",
        "`_strip_sys3`) -> `COVERED`; `system[0]`/`system[1]` are never touched by any proxy",
        "function -> `UNCLASSIFIED`.",
        "",
    ]


def _build_methodology_grouping_and_scan() -> list:
    return [
        "**Grouping.** A class = one rule code (COVERED), one known wrapper (KEEP), one tool name",
        "or the single user/assistant-text bucket (OURS), or one normalized-template signature",
        "(INJECTED / UNCLASSIFIED) — variable data (paths, IDs, counts, timestamps) normalized to",
        "placeholders before signature comparison so e.g. 50 differently-IDed background-launch",
        "acks group into one row.",
        "",
        "**Known simplification:** role=user segments are tested independently per block (not as",
        "part of the full multi-block message) — message-level gates that only look at a single",
        "block's own content (all strip passes here) are unaffected; this does not change any",
        "COVERED/KEEP decision in this corpus.",
        "",
        "**Self-scan exclusion.** The default glob excludes THIS session's own worker log",
        "(`api_requests_worker_*` embedding the current task/worktree name) — that file is written",
        "live while the script runs, so including it would make the corpus non-reproducible",
        "mid-scan. An explicit `--logs-glob` is never filtered. Any file excluded this run is listed",
        "below.",
        "",
    ]


def _build_corpus_section(file_stats: list, counters: dict, excluded_files: list) -> list:
    lines = [
        "## Corpus",
        "",
        "| File | Entries | Messages (raw) | Size |",
        "|---|---|---|---|",
    ]
    total_entries = total_messages = total_size = 0
    for fs in file_stats:
        total_entries += fs["entries"]
        total_messages += fs["messages"]
        total_size += fs["size_bytes"]
        lines.append(f"| `{fs['file']}` | {fs['entries']} | {fs['messages']} | {_fmt_bytes(fs['size_bytes'])} |")
    lines.append(f"| **Total** | **{total_entries}** | **{total_messages}** | **{_fmt_bytes(total_size)}** |")
    if excluded_files:
        lines += ["", "**Excluded (own live worker session, default glob only):**"]
        lines += [f"- `{f.name}`" for f in excluded_files]
    lines += [
        "",
        "**Chosen metric — segments** (one text/tool_result block, used for all class counts below):",
        f"raw {counters['raw_segments']:,} / distinct {counters['distinct_segments']:,} "
        f"({counters['raw_segments'] / max(counters['distinct_segments'], 1):.1f}x overcount)  ",
        "**Prior codebase metric — whole messages** `(file, exact full message content)`, for comparison:",
        f"raw {counters['raw_messages']:,} / distinct {counters['distinct_messages']:,} "
        f"({counters['raw_messages'] / max(counters['distinct_messages'], 1):.1f}x overcount)",
        "",
    ]
    return lines


def _build_summary_section(registry: dict) -> list:
    total_count = sum(r["count"] for r in registry.values())
    total_chars = sum(r["chars"] for r in registry.values())
    by_origin_n = {o: 0 for o in _ORIGIN_ORDER}
    by_origin_chars = {o: 0 for o in _ORIGIN_ORDER}
    for r in registry.values():
        by_origin_n[r["origin"]] += 1
        by_origin_chars[r["origin"]] += r["chars"]

    lines = [
        "## Summary",
        "",
        f"**Total classes:** {len(registry)}  |  **Total distinct occurrences:** {total_count:,}  "
        f"|  **Total cumulative chars:** {total_chars:,}",
        "",
        "| Origin | Classes | Distinct occurrences | Cumulative chars |",
        "|---|---|---|---|",
    ]
    for o in _ORIGIN_ORDER:
        n_cls = by_origin_n[o]
        n_occ = sum(r["count"] for r in registry.values() if r["origin"] == o)
        lines.append(f"| `{o}` | {n_cls} | {n_occ:,} | {by_origin_chars[o]:,} |")
    return lines


def _build_origin_sections(registry: dict) -> list:
    lines = []
    for origin in _ORIGIN_ORDER:
        rows = [(k, r) for k, r in registry.items() if r["origin"] == origin]
        rows.sort(key=lambda kr: -kr[1]["chars"])
        lines += [
            "",
            f"## {origin} ({len(rows)} class{'es' if len(rows) != 1 else ''})",
            "",
            "| Class | Role | Section | Block type | Distinct occ. | Cum. chars | Sample |",
            "|---|---|---|---|---|---|---|",
        ]
        for key, r in rows:
            role_s = r["role"] or "—"
            sample = _md_escape(_truncate(r["sample"] or ""))
            label = _md_escape(r["label"])
            lines.append(f"| {label} | `{role_s}` | `{r['section']}` | `{r['block_type']}` | "
                         f"{r['count']:,} | {r['chars']:,} | `{sample}` |")
    return lines


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _write_report(report: str, out_name) -> Path:
    md_dir = _SCRIPT_DIR / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    if out_name:
        out_path = md_dir / out_name
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = md_dir / f"{ts}_cc_injection_inventory.md"
    out_path.write_text(report, encoding="utf-8")
    return out_path


def _print_console_summary(registry: dict, counters: dict, out_path: Path) -> None:
    by_origin = {o: 0 for o in _ORIGIN_ORDER}
    for r in registry.values():
        by_origin[r["origin"]] += 1
    print(f"Classes: {len(registry)} total — " +
          ", ".join(f"{o}={by_origin[o]}" for o in _ORIGIN_ORDER))
    print(f"Segments: {counters['distinct_segments']:,} distinct / {counters['raw_segments']:,} raw "
          f"({counters['raw_segments'] / max(counters['distinct_segments'], 1):.1f}x overcount)")
    print(f"Report: {out_path}")
