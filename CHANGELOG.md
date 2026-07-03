# Changelog

## Unreleased

Fixes from the 2026-07 full-codebase review (review-r4; regression-tested in
`tests/test_review_r4.py`).

### Fixed

- **BOM tolerance**: a canon note hand-saved with a UTF-8 BOM (Windows
  Notepad's default) failed the frontmatter parse and silently vanished from
  every read — including its §1.7 failure memory. `node_from_markdown` now
  strips a leading U+FEFF at the single parse chokepoint.
- **Stale-edge leak on incremental reprojection**: the per-note edge diff was
  keyed on `source`, so a hand-edited note carrying an edge whose `source:`
  names another node leaked a stale `index.sqlite` row after the edge was
  removed (graph.json, rebuilt in full, disagreed). The edges table now
  carries an `owner` column (the persisting note); diff/delete key on it, a
  pre-`owner` DB reads as schema-outdated and heals via full rebuild, and
  `owner_of_edge` resolves the owning file rather than assuming
  `source == owner`.
- **§1.9 egress gaps**: the read-path re-scrub now covers `label`, kg_agenda
  `question` strings and kg_generate `rationale`s (ids stay untouched);
  kg_agenda and kg_generate route through `_scrub_egress` like the sibling
  reads; `kg_scrub` no longer counts identity (literal-placeholder) entries as
  redactions.
- A SIGKILLed PreToolUse hook could hold the canon lease past the writers'
  30 s budget on Windows (no pid probe there): the hook now declares a 15 s
  lease TTL and size-gates its synchronous reprojection (>400 notes serve the
  existing index instead of burning the 5 s cap on every read, forever).
- The divergence `ingest` now parses candidates and warm-loads the embedder
  BEFORE taking the project lock, so the first-use ~120 MB model download can
  no longer outlive the lock's 60 s staleness window and get it stolen
  mid-cycle.
- `backend.run()`'s post-run projection is guarded: a projection failure is
  recorded as `projection_error` in the summary instead of masking the run's
  own exception from the `finally`.
- `export._bridge_set` tie-breaks by id ASCENDING among equal
  `spec_betweenness`, matching kg_context's `ORDER BY … id ASC`.
- `advisory_geometry`'s `grounded_mix` counts incoming edges too
  (`G.edges(node)` is out-only on a MultiDiGraph).
- `build_engine_from_env` filters unsubstituted `${…}` values from
  `CLAUDE_PLUGIN_OPTION_*` reads, like every other env read.
- Divergence `_atomic_write` guards its temp-file cleanup so an unlink failure
  can't mask the real write error (parity with `atomicio`).

### Changed

- `run_generators` size-gates the exact convergence tally at
  `FULL_TALLY_MAX_NODES` (400): above it, mechanisms run at the surfaced `k`
  instead of materializing O(V²) candidates; the surfaced slate is identical.
- `kg_write` now reuses a cheap-signature-keyed canon baseline across calls
  (the server-side twin of backend-1), so a parallel `/kg-build` wave no
  longer re-parses the whole canon per write; any out-of-band write
  invalidates it.
- Depend on `igraph` directly (the `python-igraph` name is a deprecated PyPI
  alias for the same package).

### Docs

- Scrubbed the stale references to the donor's `ARCHITECTURE.md` (deliberately
  not vendored — see ATTRIBUTION.md) from SKILL.md, `references/contract.md`
  and two engine comments; the contract.md note on provenance demotion now
  states what `boundary.py` actually does (provenance is left exactly as
  declared). Added `CLAUDE.md` (repo guide for Claude Code).

### Tests

- New `tests/test_review_r4.py` regression file (12 tests) covering all of the
  above; the divergence-firewall pre-port guard now fails loudly instead of
  silently passing if the package stops resolving; a `sys.modules` stub leak,
  a duplicated helper, a byte-identical duplicate test, a module-level
  `sys.path` mutation and a vacuous sleep-based "writer blocks" assertion were
  cleaned up; `test_alpha_threshold_semantics` now actually tests the
  reliability threshold (and documents Krippendorff's rare-category zero).


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
