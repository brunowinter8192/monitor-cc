#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT"
PY="$ROOT/dev/pdf_conversion_qa/venv/bin/python"
RUN="$ROOT/dev/pdf_conversion_qa/03_run_candidate.py"
stage="$1"
case "$stage" in
  cheap)
    for rep in 1 2 3; do
      for c in C4a C4b C5a C5b; do caffeinate -i "$PY" "$RUN" --candidate "$c" --select all --rep "$rep"; done
    done ;;
  calibration)
    for rep in 1 2 3; do
      for c in C1 C2 C3; do caffeinate -i "$PY" "$RUN" --candidate "$c" --select calibration --rep "$rep"; done
    done ;;
  c1)
    caffeinate -i "$PY" "$RUN" --candidate C1 --select all --rep 1 ;;
  c1panel)
    for rep in 2 3; do caffeinate -i "$PY" "$RUN" --candidate C1 --select panel --rep "$rep"; done ;;
  c2)
    caffeinate -i "$PY" "$RUN" --candidate C2 --select failed-of:C1 --rep 1
    for rep in 1 2 3; do caffeinate -i "$PY" "$RUN" --candidate C2 --select panel --rep "$rep"; done ;;
  whole)
    caffeinate -i "$PY" "$ROOT/dev/pdf_conversion_qa/06_run_whole_docs.py" ;;
  c3)
    caffeinate -i "$PY" "$RUN" --candidate C3 --select all --rep 1
    for rep in 2 3; do caffeinate -i "$PY" "$RUN" --candidate C3 --select panel --rep "$rep"; done ;;
esac
echo STAGE_DONE "$stage"
