# Blockers, Deferrals, Rejections

Statuses: `DEFERRED` (non-critical, no later stage depends on it) · `REJECTED-BY-PLAN` (explicitly out of scope, e.g. Non-Goal 1 embedding-as-retrieval ideas) · `FUTURE` (good idea, post-release).

- `FUTURE` — **Generator-facing geometry labels**: the Stage-6 blind experiment showed the dpp arm's raw label values (bins, semantic_novelty, cliche_distance numbers) leak into generated ideas as unsupported apparatus-jargon (EXPERIMENT.md, "Observed mechanism"). Candidate refinement: render advisory labels to the human only (or strip numeric values from the generator-facing block), then re-run the D1 experiment. Out of scope for 0.1.0 — the flag ships OFF per D1.
