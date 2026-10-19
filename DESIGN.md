# CausalForge Design Notes

## Product intent
CausalForge makes builds temporal dependency graphs that connect execution errors to ranked root causes and incident blast radius practical in a reviewable developer workflow. It favors compact source data, deterministic scoring and reports that retain the evidence behind every result.

## Design principles
1. **Traceable results** — every score connects to normalized input records and named calculations.
2. **Portable artifacts** — JSON and Markdown reports travel cleanly through pull requests and release notes.
3. **Compositional analysis** — parsers, domain models, metrics and renderers can evolve independently.
4. **Useful defaults** — bundled fixtures demonstrate realistic workflows without configuration overhead.

## Engine parity
The Python package is the reference implementation. The C++ core mirrors the
scoring math so embedders can run the same ranking without a Python runtime;
the `.events` fixture is the contract both sides are checked against. The core
is built manually (see the README recipe) rather than shipped as a Python
extension.

## Extension seams
New record adapters belong at the ingestion boundary, new metrics attach to the analysis summary, and new renderers consume the existing report model. This keeps integrations focused and avoids cross-cutting rewrites.

