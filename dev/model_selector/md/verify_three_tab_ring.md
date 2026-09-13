# Models tab — three-tab ring verification — 2026-09-13T16:06:15

## Forward: Sessions -> RAG -> Models -> Sessions (Cmd+->)
open main: panel_open=True
Cmd+-> from main: now on rag
Cmd+-> from rag: now on models
Cmd+-> from models: back on main (ring closes)

## Reverse: Sessions -> Models -> RAG -> Sessions (Cmd+<-)
Cmd+<- from main: now on models
Cmd+<- from models: now on rag
Cmd+<- from rag: back on main (ring closes)

RESULT: PASS — three-tab ring (Sessions/RAG/Models) correct in both directions, against the real _open_*_panel/_close_*_panel/_deferred_close_open functions.
