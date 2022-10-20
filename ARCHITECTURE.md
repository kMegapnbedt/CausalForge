# CausalForge Architecture

CausalForge is a AI Failure Causality Explorer that builds temporal dependency graphs that connect execution errors to ranked root causes and incident blast radius. The repository uses a Python orchestration layer and a focused native companion so input normalization, deterministic analysis and report rendering remain easy to inspect.

## System flow

`	ext
fixtures or operator input -> parser -> normalized domain records -> analysis engine -> report model -> terminal / JSON / Markdown
` 

## Components

- **Python package** owns command handling, portable parsers, report assembly and example workflows.
