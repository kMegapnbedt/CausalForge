"""CausalForge — AI Failure Causality Explorer.

CausalForge ingests execution events and their dependencies, assembles a
directed causal graph, and ranks the nodes most likely to be the *origin* of
an incident. The scoring model blends three signals:

* **Temporal propagation** — blame flows backward from failing sinks toward
  upstream causes, attenuated by an exponential time-decay kernel so that
  events which finished long before a downstream failure are down-weighted.
* **Error evidence** — locally observed error weight (exception counts, log
  severity, retry storms) is folded into each node's suspicion score.
