# Burgess

![burgess-with-fossils.png](images/burgess-with-fossils.png)

**The full creative cycle in one Claude Code plugin: diverge without collapsing to the mean, converge without believing your own ideas.**

Burgess fuses two engines around one boundary:

- a **convergence engine** (from [Sproutgraph](https://github.com/sergiparpal/Sproutgraph)) that grows source documents into a rigorously grounded, queryable knowledge graph — human-editable canon, three-axis provenance, a span-present write boundary, a grounding loop with permanent memory of failures, and a regenerable NetworkX/SQLite derived layer;
- a **divergence engine** (from [Cambrian](https://github.com/sergiparpal/Cambrian)) that turns any brief into a diverse, non-cliché slate of ideas — a local, server-less MAP-Elites archive with k-NN geometric novelty, DPP slate selection, and an anti-collapse monitor, with you steering and selecting in chat.

The name is the thesis: the **Burgess Shale** is where the Cambrian explosion's forms were preserved in stone — divergence and grounding in one word.

One sentence resolves every design dispute in this codebase: **embeddings measure dispersion, never truth.**

## Install

```text
/plugin marketplace add sergiparpal/Burgess
/plugin install burgess@sergiparpal
```

For local development, point Claude Code at a checkout instead:

```bash
claude --plugin-dir /path/to/Burgess
```

On first load a SessionStart hook provisions a local Python venv (Python ≥ 3.11 recommended; `uv` preferred, stdlib `venv`+`pip` fallback) in the plugin's persistent data dir. Everything runs locally; the divergence embedder is [model2vec](https://github.com/MinishLab/model2vec) `potion-multilingual-128M` (CPU, torch-free, ~120 MB, cached after first download).

## The fused pipeline

```text
/kg-diverge <brief>        pure divergence — no graph, no source document required
      │  cliché map → mechanism-first generation (the agent) →
      │  embed → MAP-Elites bins → k-NN novelty → DPP slate (the engine) →
      │  you pin / discard / answer A-vs-B in chat, monitor watching
      ▼
 pins materialize          explicit action, propose lane ONLY → provenance=hypothesized,
      │                    epistemic_state=unverified, lineage in the body; no source? they wait
      ▼
/kg-ground                 the ONLY verdict path: promotion needs support (a verbatim span or
      │                    citation); failures become PERMANENT negative memory — and flow back
      │                    into the brief's discards, so failed ideas are never re-proposed
      ▼
/kg-generate               seven structural mechanisms propose from the graph itself; with
                           divergence.dpp on, the same slate is presented in advisory-DPP order
                           with geometry labels (measured blind; see docs/fusion/EXPERIMENT.md)
```

Plus everything the convergence side always did: `/kg-build`, `/kg-query`, `/kg-eval`, `/kg-experiment` (now with a `graph+generate+dpp` arm), `/kg-perturb`, `/kg-view`.

## Commands

| Command | What it does |
|---|---|
| `/kg-build` | Extract a span-anchored graph from your source document (wave-parallel extractors) |
| `/kg-ground` | Run the grounding loop: verdicts, promotions with support, permanent failure memory |
| `/kg-diverge` | Diverge from any brief into a non-cliché slate; pins/discards; optional materialization |
| `/kg-generate` | Propose hypothesized candidates from graph structure (7 mechanisms; optional DPP presentation) |
| `/kg-query` | Query the grounded graph (context packs, paths, neighbors, agenda) |
| `/kg-eval` | Precision/agreement/specificity evaluation harness |
| `/kg-experiment` | Blind multi-arm ideation experiment (control / graph / graph+generate / graph+generate+dpp / rag) |
| `/kg-perturb` | Build a second construction and cross-generate against it |
| `/kg-view` | Render the offline graph.html + report |

## Architecture in six invariants

1. **Verdict monopoly** — only `kg_ground` produces verdicts; nothing in `kg_engine/divergence/` can set or upgrade an epistemic state (import-firewall-tested, adversarially attacked in the suite).
2. **Span-present boundary** — no span-less `grounded` edge can exist; forged verdicts are stripped at the boundary and re-quarantined by the reconciler.
3. **Advisory ceiling** — DPP order, novelty, cliché distance, bins, monitor readings influence *what is proposed and in what order*, never *what is true* (snapshot-tested: grounding output is bit-identical with the geometry flag on vs off).
4. **Different-family judge** — the diversity embedder (model2vec) never shares lineage with the generator (Claude), so the geometry can't just agree with the model that made the ideas.
5. **Session-ephemeral archives** — MAP-Elites archives never persist across sessions; only pins, discards, comparisons and session metadata do (project-local, git-friendly, under `.kg/diverge/`). The knowledge graph is the durable archive.
6. **Unified negative memory** — human discards and grounding failures live in one semantic store; neither generation path ever re-proposes from it.

The knowledge-graph spine: canon = one human-editable Markdown file per node (git-mergeable, semantic merge driver); derived = regenerable NetworkX/SQLite projections; MCP server (`burgess`, 27 tools) is the trust boundary; six subagents (extractor, grounder, adversarial-grounder, generator, annotator, evaluator) do the language work; the engine stays deterministic.

The full, self-contained architecture reference — module map, data model, write-boundary contract, tool surface, divergence internals and constants, runtime and environment — is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## What this does not guarantee

In the spirit of both donors, honestly:

- **Grounding guarantees fidelity to your source, never truth about the world.** A grounded edge means a verbatim span supports it in *your* document — not that the document is right.
- **Novelty numbers are variety proxies.** `novelty` is k-NN distance to *this session's own ideas*; `originality` is distance to *the agent's own* guess at the clichés. Neither is novelty against prior art or the world.
- **The cliché map hedges cliché; it does not guarantee freshness.** "Obvious" is the model's notion of obvious.
- **The judge is bounded, not infallible.** Validity filtering is clipped to a [0.7, 1.3] multiplier at weight 0.3 — it can nudge, it cannot veto diversity; bad ideas can still reach you (that's the point: you are the selector).
- **The DPP presentation is advisory.** Whether it actually lifts downstream ideation was measured blind (see `docs/fusion/EXPERIMENT.md`); the shipped default follows that measurement, not our enthusiasm.

## Tests

<!-- test-count:begin -->
The suite currently reports: **1066 passed, 2 skipped** (`uv run --extra dev pytest tests/`).
<!-- test-count:end -->

This line is generated from pytest output, never hand-written. Run it yourself:

```bash
uv sync --extra dev   # or: pip install -e ".[dev]"
uv run pytest tests/
```

The fusion invariants live in `tests/fusion/` (import firewall, DB isolation, adversarial forge attempts, graceful degradation, archive ephemerality, snapshot invariance, verdict neutrality); the divergence engine's ported suite in `tests/fusion/divergence/`; the vendored convergence suite at `tests/`.

## Lineage

Burgess is a fusion of two MIT-licensed plugins by the same author, both of which continue as independent projects:

- **Sproutgraph** — <https://github.com/sergiparpal/Sproutgraph> — the convergence spine (engine, MCP boundary, commands, agents, experiment harness, canon/derived model), vendored at `17c4066`.
- **Cambrian** — <https://github.com/sergiparpal/Cambrian> — the divergence engine (embedder, MAP-Elites, novelty, DPP, monitor, judge bounds, cliché discipline), vendored at `a2adfa1`.

Per-file attribution with SHAs and every adaptation: [`docs/fusion/ATTRIBUTION.md`](docs/fusion/ATTRIBUTION.md). Migrating from either donor: [`docs/MIGRATION.md`](docs/MIGRATION.md). How this plugin was built (the full fusion plan and its decision log): [`docs/fusion/FUSION_PLAN.md`](docs/fusion/FUSION_PLAN.md) + [`docs/fusion/`](docs/fusion/).

## License

MIT — see [LICENSE](LICENSE).
