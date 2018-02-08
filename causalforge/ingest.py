"""Incident ingestion.

Two input formats are supported, both parsed with the standard library only:

* **JSON incident** (``docs/schema.md``) — the canonical, rich format loaded by
  :func:`load_incident`.
* **Compact event log** — one event per line, shared with the C++ engine, parsed
  by :func:`parse_events`. Handy for streaming from shell pipelines.
