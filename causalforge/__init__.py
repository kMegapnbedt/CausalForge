"""CausalForge — AI Failure Causality Explorer.

CausalForge ingests execution events and their dependencies, assembles a
directed causal graph, and ranks the nodes most likely to be the *origin* of
an incident. The scoring model blends three signals:

* **Temporal propagation** — blame flows backward from failing sinks toward
  upstream causes, attenuated by an exponential time-decay kernel so that
