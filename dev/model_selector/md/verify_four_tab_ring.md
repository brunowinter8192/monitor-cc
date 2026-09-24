# Four-tab ring verification — 2026-09-24T22:33:39

## Forward: Sessions -> RAG -> Models -> Launch -> Sessions (Cmd+->)
open main: only main open
Cmd+-> from main: now on rag
Cmd+-> from rag: now on models
Cmd+-> from models: now on launch
Cmd+-> from launch: now on main

## Reverse: Sessions -> Launch -> Models -> RAG -> Sessions (Cmd+<-)
Cmd+<- from main: now on launch
Cmd+<- from launch: now on models
Cmd+<- from models: now on rag
Cmd+<- from rag: now on main

RESULT: PASS — four-tab ring (Sessions/RAG/Models/Launch) correct in both directions, against the real _open_*_panel/_close_*_panel/_deferred_close_open functions.
