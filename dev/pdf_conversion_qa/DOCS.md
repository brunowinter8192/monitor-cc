# dev/pdf_conversion_qa/

## Role
Measurement harness that compared PDF-to-Markdown converters (MinerU variants, pymupdf4llm, liteparse) on a fixed page sample and on whole wise2627 PDFs: crashes, speed, memory, text recall and cleanup-class counts. Touch to rerun or extend the comparison; not production code.

## Public Interface
No `__init__.py` exports. Entry points are the numbered scripts, run in order from the repo root with the dev venv; `run_stage.sh` runs a named stage. Proposed skill change lives in `patch/`.

## Flow
Source PDFs → `01` slices sample windows → `02` extracts the pdftotext reference → `03`/`06` run candidates per window or whole document under a memory probe → `04` computes metrics → `05`/`07` write reports to `md/`, raw rows to `json/` and `csv/`.

## Modules

### 00_detokenizer_check.py (47 LOC)

**Purpose:** Proves the mlx_vlm detokenizer UTF-8 crash unpatched and its absence with the injected one-line patch.
**Reads:** `detokenizer_probe.py`, `patch/`.
**Writes:** `json/00_detokenizer_check.json`.
**Called by:** CLI.
**Calls out:** MinerU venv python.

---

### 01_build_sample.py (202 LOC)

**Purpose:** Slices the sample windows from the source PDFs and writes the manifest.
**Reads:** wise2627 and Trading PDFs under rag-cli `data/pdf/`.
**Writes:** `samples/` (gitignored), `json/01_build_sample.json`.
**Called by:** CLI.
**Calls out:** pypdf.

---

### 02_extract_reference.py (78 LOC)

**Purpose:** Extracts the per-page pdftotext reference layer and eligibility flags.
**Reads:** sample PDFs.
**Writes:** `reference/` (gitignored), `json/02_extract_reference.json`.
**Called by:** CLI.
**Calls out:** poppler `pdftotext`.

---

### 03_run_candidate.py (90 LOC)

**Purpose:** Runs one or more candidates over the sample windows.
**Reads:** manifest.
**Writes:** `runs/` (gitignored), `json/03_run_candidate.jsonl`.
**Called by:** CLI, `run_stage.sh`.
**Calls out:** none beyond `candidates.py`.

---

### 04_metrics.py (98 LOC)

**Purpose:** Computes recall, special-character and umlaut recall, length ratio and cleanup-class counts per run.
**Reads:** run outputs, reference.
**Writes:** `csv/04_metrics.csv`, `csv/04_metrics_whole.csv`.
**Called by:** CLI.
**Calls out:** none.

---

### 05_report.py (325 LOC)

**Purpose:** Writes the measurement report.
**Reads:** `json/`, `csv/`.
**Writes:** `md/05_report.md`, `json/05_report.json`.
**Called by:** CLI.
**Calls out:** none.

---

### 06_run_whole_docs.py (52 LOC)

**Purpose:** Runs the cheap candidates on all wise2627 PDFs as whole documents.
**Reads:** wise2627 PDFs.
**Writes:** `json/06_run_whole_docs.jsonl`.
**Called by:** CLI, `run_stage.sh`.
**Calls out:** none beyond `candidates.py`.

---

### 07_char_diagnosis.py (65 LOC)

**Purpose:** Diagnoses which characters a candidate loses against the reference.
**Reads:** run outputs, reference.
**Writes:** `md/07_char_diagnosis.md`.
**Called by:** CLI.
**Calls out:** none.

---

### candidates.py (185 LOC)

**Purpose:** Command lines and run logic per candidate.
**Reads:** `config.py` constants.
**Writes:** candidate output under `runs/`.
**Called by:** `03_run_candidate.py`, `06_run_whole_docs.py`.
**Calls out:** MinerU binary, `cheap_worker.py` in the dev venv.

---

### cheap_worker.py (112 LOC)

**Purpose:** Runs pymupdf4llm or liteparse on one PDF inside the dev venv.
**Reads:** one PDF, `tessdata/`.
**Writes:** output md, page offsets.
**Called by:** `candidates.py` (subprocess).
**Calls out:** pymupdf4llm, pymupdf, liteparse.

---

### runner.py (117 LOC)

**Purpose:** Monitored subprocess run, MinerU flock and fast_api teardown.
**Reads:** `~/.mineru-locks/mineru.flock`.
**Writes:** traces via `memory_probe.py`.
**Called by:** `candidates.py`.
**Calls out:** none.

---

### memory_probe.py (148 LOC)

**Purpose:** Samples phys_footprint of a process tree and system available memory.
**Reads:** `/usr/bin/footprint`, process table.
**Writes:** `traces/` (gitignored).
**Called by:** `runner.py`.
**Calls out:** psutil.

---

### text_metrics.py (75 LOC)

**Purpose:** Normalisation and character-recall helpers.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `02_extract_reference.py`, `04_metrics.py`, `07_char_diagnosis.py`, `tests/test_metrics.py`.
**Calls out:** none.

---

### cleanup_classes.py (102 LOC)

**Purpose:** Counts the websearch-pdf cleanup classes in a Markdown text.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `04_metrics.py`, `tests/test_metrics.py`.
**Calls out:** none.

---

### config.py (54 LOC)

**Purpose:** Shared paths and candidate lists of the harness.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** all numbered scripts and helpers.
**Calls out:** none.

---

### detokenizer_probe.py (54 LOC)

**Purpose:** Feeds the mlx_vlm detokenizer split multibyte tokens.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `00_detokenizer_check.py` (subprocess).
**Calls out:** mlx_vlm.

---

### run_stage.sh (30 LOC)

**Purpose:** Runs a named measurement stage with caffeinate.
**Reads:** stage name.
**Writes:** stage logs.
**Called by:** CLI.
**Calls out:** dev venv python.

---

### patch/sitecustomize.py (67 LOC)

**Purpose:** Injected at runtime to apply the one-line detokenizer fix in the MinerU process.
**Reads:** nothing.
**Writes:** a marker file per patched pid.
**Called by:** MinerU processes started with `patch/` on PYTHONPATH.
**Calls out:** mlx_vlm.

---

### tests/test_metrics.py (40 LOC)

**Purpose:** Tests recall and cleanup-class helpers.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** pytest.
**Calls out:** pytest.

---

## State
None shared. Gitignored working data: `venv/`, `tessdata/`, `samples/`, `reference/`, `runs/`, `traces/`.
