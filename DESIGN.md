# CausalForge Design Notes

## Product intent
CausalForge makes builds temporal dependency graphs that connect execution errors to ranked root causes and incident blast radius practical in a reviewable developer workflow. It favors compact source data, deterministic scoring and reports that retain the evidence behind every result.

## Design principles
1. **Traceable results** — every score connects to normalized input records and named calculations.
2. **Portable artifacts** — JSON and Markdown reports travel cleanly through pull requests and release notes.
3. **Compositional analysis** — parsers, domain models, metrics and renderers can evolve independently.
4. **Useful defaults** — bundled fixtures demonstrate realistic workflows without configuration overhead.

## Event-stream metadata
The compact stream is deliberately headerless today: fixtures stay readable and
the C++ parser has one grammar to learn. Any metadata that survives a round
trip must therefore be carried in a new leading record (`H ...`), parsed
leniently and ignored by readers that do not know it yet.

## Extension seams
New record adapters belong at the ingestion boundary, new metrics attach to the analysis summary, and new renderers consume the existing report model. This keeps integrations focused and avoids cross-cutting rewrites.

