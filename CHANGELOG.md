# Changelog

## 0.1.0 — first release (2026-07-02)

Burgess 0.1.0 is the first release of the fused plugin: Sproutgraph's grounded
knowledge-graph convergence engine and Cambrian's diversity-preserving
divergence engine, one MCP trust boundary, one domain-pack format.

### The spine (vendored from Sproutgraph @ `17c4066`)

- Deterministic graph engine (`scripts/kg_engine/`, 20 modules): canon/derived
  split, span-present write boundary, `kg_ground` verdict monopoly, reconciler
  re-quarantine, span-staleness advisory, egress scrub, experiment harness.
- 8 slash commands, 6 subagents, SessionStart provisioning chain (uv + pip
  fallback), PreToolUse grounded-context injection, offline graph.html export.
- Full donor test suite green at exact baseline parity (731 passed, 2 skipped)
  before any fusion work landed.

### The divergence engine (vendored from Cambrian @ `a2adfa1`)

- `kg_engine/divergence/` (15 modules + importer): model2vec static embedder
  (`potion-multilingual-128M`; deterministic hash embedder for tests/offline),
  MAP-Elites archive with CVT open-axis niching, k-NN geometric novelty, greedy
  DPP slate selection with farthest-point fallback, anti-collapse monitor
  (entropy + mean pairwise cosine) with variety-erosion early warning, bounded
  judge influence (weight 0.3, fitness clip [0.7, 1.3] — donor constants,
  drift-guarded), advisory originality/gap probes, per-domain descriptor axes.
- All donor engine tests ported and green (226 tests).

### New in the fusion

- **`/kg-diverge`** — standalone divergence with no graph and no source
  required: cliché map (held-out split), mechanism-first generation, DPP slates
  with honest novelty semantics, pins/discards/A-vs-B, monitor reactions.
  Engine exposed as six `kg_diverge_*` MCP tools; project-local state under
  `.kg/diverge/` (explicitly not `~/.cambrian`); session-ephemeral geometry
  (a new session wipes the archive; pins/discards/comparisons survive).
- **Pin materialization** (`kg_diverge_materialize`) — the explicit door from
  divergence into the graph: pins become `provenance=hypothesized,
  epistemic_state=unverified` nodes via the propose lane exclusively, with full
  `[diverge]` lineage; promotion still requires support; verdict-neutral pin
  priority in the grounding queue.
- **Unified negative memory** — grounding failures of materialized pins flow
  back into the brief's discards automatically; neither `/kg-diverge` nor
  `/kg-generate` ever re-proposes from the failure store.
- **Advisory DPP over `/kg-generate`** — behind `divergence.dpp` (pack flag +
  per-call override): hybrid descriptors (semantic novelty + community /
  graph-distance / grounded-mix axes), grounded-hub cliché map, judge-bounded
  DPP ordering. Snapshot-enforced advisory: grounding output is bit-identical
  flag on vs off.
- **`graph+generate+dpp` experiment arm** + `dpp_verdict` in the harness; the
  shipped `divergence.dpp` default was decided by the pre-declared blind rule
  D1 (see `docs/fusion/EXPERIMENT.md`).
- **One domain-pack format** — `pack.yaml` carries the extraction vocabulary
  AND an optional `divergence:` section (behavior axes + flags); Cambrian's
  domain templates ship as pack fragments under `pack/domains/`.
- **State importer** — `python -m kg_engine.divergence import-cambrian` maps an
  old `~/.cambrian` project's pins/discards/comparisons into `.kg/diverge/`
  (read-only on the source).

### Invariants, enforced by tests before the features they guard

Verdict monopoly (I1), span-present boundary (I2), import firewall (I3), DB
isolation — no vector schema anywhere the query tools read (I4), advisory
ceiling with bit-identical grounding snapshots (I5), donor judge bounds (I6),
different-family embedder (I7), sticky + consulted negative memory (I8),
graceful degradation — every kg_* tool works with divergence deps blocked (I9),
session-ephemeral archives (I10), donors untouched (I11 — gate scripted and
green at every commit).
