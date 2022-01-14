# CausalForge Design Notes

## Product intent
CausalForge makes builds temporal dependency graphs that connect execution errors to ranked root causes and incident blast radius practical in a reviewable developer workflow. It favors compact source data, deterministic scoring and reports that retain the evidence behind every result.

## Design principles
1. **Traceable results** — every score connects to normalized input records and named calculations.
