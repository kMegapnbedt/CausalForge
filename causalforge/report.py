"""Investigation report rendering.

Produces two artefacts from a ranked incident:

* **Markdown** — a human-readable investigation with a suspect table, timeline
  strip, and per-suspect rationale, ready to paste into a postmortem doc.
* **JSON** — a machine-readable investigation for downstream automation.
