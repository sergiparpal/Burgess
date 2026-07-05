# Changelog

## Unreleased

### Added

- **Re-examinable-verdicts advisory (R3-mirror) for non-monotonic evidence.**
  Grounding verdicts are permanent negative memory and the grounder never
  revisits them; the only source-change reaction (the R3 stale-verdict advisory)
  fired one direction — a `grounded`/`failed` span-present edge whose span
  *disappeared*. A new **read-only** mirror flags the opposite case: a
  `failed`/`rejected` item — **nodes and span-less items included, which R3
  cannot cover** — that was judged against a source set which has since **grown
  or changed**, so it may now be supportable and deserves a re-look. It **never
  mutates a verdict and never re-queues** (re-grounding stays a `kg_ground`
  decision); a term-overlap filter keeps only items the changed source actually
  mentions. Surfaced in `kg_context.advisory.reexaminable_verdicts` and a
  `## Re-examinable verdicts` GRAPH_REPORT section (new projector meta keys
  `reexaminable_verdicts` + `source_file_sigs`; no model schema change; R3 and
  the global `FAILURE_STATES` untouched). The divergence side mirrors it:
  `failed`-fated brief discards are surfaced as `reexaminable_discards` on a
  source change, with an **explicit** un-seal lever
  `kg_diverge_recall(project, reexamine=[candidate_ids])` (never auto-un-sealed).
  Pinned in `tests/test_reexaminable_verdicts.py` (9 tests) and
  `tests/fusion/test_materialization.py` (4 new tests).

### Fixed

- **Grounding no longer permanently buries novel `/kg-diverge` pins.**
  `_sync_materialized_fates` folded a materialized pin into its brief's
  **permanent** discards whenever its canon item reached the global
  `FAILURE_STATES` (`{rejected, failed}`) — so grounding a genuinely novel pin
  against the original source (which yields `rejected`: no in-source span, the
  *expected* state of novelty) discarded it **for being novel**. A new, narrower
  `server.MATERIALIZED_DISCARD_STATES = {failed}` now keys the fold: only an
  actively **falsified** pin discards; a merely **unsupported** pin stays
  recoverable in the lane until sources are added. Verdict neutrality is
  preserved (the change is in the diverge-brief-local *consequence*, not the
  verdict); the global `FAILURE_STATES` and the write-boundary durability
  quarantine backing `/kg-generate` negative memory are untouched. The
  `kg-grounder` prompt now leaves unsupported `[diverge]`-lineage edges
  `unverified` (triage), and `kg_diverge_materialize` returns an advisory-only
  note when a source is already configured. Pinned in
  `tests/fusion/test_materialization.py` (5 new tests, mutation-verified).

## 0.1.2 — 2026-07-04

Hardening release: the full 2026-07 review trilogy — maintainability
(review-r5), performance (review-r6), and correctness (review-r7) — plus a
documentation pass that makes the docs self-contained and drift-free against
the engine source. No user-facing API or tool-surface changes.

### Changed

- **2026-07 maintainability review (review-r5)**: ~45 findings applied — single
  homes for duplicated logic (`envconfig`, `dirlock`, `pathing`,
  `sources.split_sections`, failure-state vocabulary, `node_content_hash`, the
  derived-layer reader), decompositions of the largest functions (reconciler
  `scan`, divergence ingest, canon `write_nodes`, `run_generators`, bootstrap
  install), and clarity renames. Pinned in `tests/test_review_r5.py`
  (23 tests, including JS↔Python env-resolution parity).
- **2026-07 performance review (review-r6)**: lazy heavy imports (server import
  ~190 ms → ~60 ms), binary `.npz` divergence vector stores (legacy `.json`
  still read, migrated on next write), capped mechanism-spread computation,
  lazy-row farthest-point selection, stat-gated incremental canon parsing,
  glossary term cap + SQL LIMIT, and fsync skipped for session-ephemeral state.
  Pinned in `tests/test_review_r6.py`.

### Fixed

- **2026-07 correctness review (review-r7)**: 7 verified findings fixed and
  pinned in `tests/test_review_r7.py` (21 tests):
  - `model.py` frontmatter regex: the closing-fence `\s*` greedily ate the
    body's first-line indentation, making `node_from_markdown`∘`node_to_markdown`
    lossy (a 4-space code block lost its first line) and silently defeating
    canon's idempotent-no-op write guard (`node_content_hash` mismatch →
    spurious rewrite + timestamp-only commit). Now horizontal-whitespace-only.
  - `server.py` egress: `kg_write`, `kg_rename`, and `kg_merge` returned the
    canon rollback reason (`info.error`) unscrubbed, leaking an absolute vault
    path across the §1.9 boundary that every sibling error-return scrubs (the
    `_tool_result` envelope scrubs raised exceptions, not returned dicts). All
    three now route through `_scrub_error`.
  - `export.py`: chained `.replace()` rescanned the inlined data payload, so a
    node label equal to the `__KG_FAILURE_STATES_JSON__` sentinel corrupted the
    graph.html JSON. Now a single-pass `re.sub` that never rescans replacements.
  - `harness.py`: the `ideation`/`convergence`/`specificity` CLIs crashed with
    an uncaught `AttributeError`/`TypeError` on a malformed top-level JSON shape
    (array/scalar) instead of the clean exit-2 usage error `agreement` emits.
  - `generate.py`: `run_generators` was defined twice; the duplicate shadowed
    the first def and the review-r5 module-level helpers (`_convergence_tally`,
    `_dedup_candidates`, `_edge_key`), leaving them dead. The duplicate is
    removed so the module-level helpers are live and testable in isolation.
  - `agents/evaluator.md` / `commands/kg-experiment.md`: granted `kg_generate`,
    which the kg-evaluator is instructed to call for the graph+generate+dpp arm.
  - `commands/kg-ground.md` Stage 0b: the stale-verdict remedy prescribed
    `kg_ground(grounded, support_span=…)`, which is a no-op for a span-present
    edge (support_* only promote hypothesized items), so the flag never cleared;
    it now relocates the span via `kg_write` (a canon edit that re-opens
    grounding).
- Completed the I5 clock freeze in the test suite: canon's `utcnow` binding
  leaked wall time into the frozen-clock snapshot tests.

### Docs

- **`docs/ARCHITECTURE.md`** — new self-contained architecture reference
  written from the engine source (module map, data model, boundary
  dispositions, verdict path, derived layer, divergence internals with the
  shipped constants, tool surface, env contract, provisioning/supervision,
  invariants). The documentation no longer relies on either donor's docs.
- `references/tools.md`: new §1B documenting the seven `kg_diverge_*` tools
  (parameters, return shapes, `.kg/diverge/` state layout, session
  ephemerality, engine constants) and §2.4 for the
  `python -m kg_engine.divergence` CLI incl. the selftest gates and importer
  report; `kg_generate`'s `dpp` parameter and `divergence_advisory` block
  documented; the harness section now covers all four subcommands
  (`convergence` was missing) and the full ideation arm list.
- `references/pack-schema.md`: the optional `divergence:` pack section is now
  part of the documented `PackContract` (shape-check vs deep-validation split
  per the I3 firewall); `pack/domains/_schema.md` stale pre-fusion paths
  (`config/domains/…`) corrected to `pack/domains/…`.
- `docs/MIGRATION.md` made self-contained: the selftest gates/margins, importer
  report shape, and every carried-over engine constant are stated in-file
  instead of deferring to "the donor's" values.
- SKILL.md: stale hand-written test count removed (the README's generated count
  is the single home), the `graph+generate+dpp` experiment arm added, and the
  references index now lists all six reference files.
- Donor-relative phrasings scrubbed from `commands/kg-generate.md`,
  `commands/kg-experiment.md`, and `references/contract.md`.
- `FUSION_PLAN.md` relocated from the repo root to `docs/fusion/`, joining the
  rest of the fusion decision record.
- **2026-07-04 doc drift-audit** (full doc↔source audit, adversarially
  verified): corrected six stale claims — the vendored Sproutgraph engine
  module count 20 → 21 (`docs/fusion/ATTRIBUTION.md`, `docs/fusion/INVENTORY.md`,
  and this changelog's 0.1.0 spine entry; the donor @`17c4066` has 21 top-level
  `.py` files, matching the sibling Cambrian "15 modules" convention);
  `references/contract.md`'s core-tool count "eleven" → "sixteen" (`server.py`
  exposes 16 core + 4 generative graph tools); `references/tools.md`'s
  `kg_generate` `divergence_advisory` block, now documented as the parallel
  `bins`/`semantic_novelty`/`cliche_distance` arrays plus
  `beyond_cap_kept_in_donor_order` that `advisory_geometry.py` returns (not a
  `candidates` list); and a missing `Bash` grant in `/kg-ground`'s frontmatter,
  whose Stage-0 note runs `python -m kg_engine.harness convergence`.

## 0.1.1 — 2026-07-03

Patch release: every finding from the 2026-07 full-codebase review (review-r4;
regression-tested in `tests/test_review_r4.py`), plus a stale-doc scrub and a
CLAUDE.md repo guide.

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

- Deterministic graph engine (`scripts/kg_engine/`, 21 modules): canon/derived
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
