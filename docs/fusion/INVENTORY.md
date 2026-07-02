# Donor Code Inventory

Concept → actual-donor-code map, built from donor **code** (never README prose) at the pinned SHAs (see BASELINE.md). Every FUSION_PLAN.md "(verify)" expectation is resolved here; mismatches are flagged **DISCREPANCY**. All file:line references are relative to the donor repos at their pinned SHAs.

---

# Part I — Cambrian @ `a2adfa1` (divergence donor)

Engine package: `skills/ideate/scripts/cambrian_engine/` (version 0.5.1). **DISCREPANCY (plan §2.5):** plan expected module `cambrian_engine` at an unspecified path — actual location is under the skill: `skills/ideate/scripts/`. `python -m cambrian_engine` works once that dir is on `sys.path`/installed.

## C1. Engine modules

| Module | Responsibility |
|---|---|
| `__main__.py` | argparse CLI; subcommands: `init-project`, `paths`, `recall`, `ingest`, `remember`, `parents`, `metrics`, `selftest` (JSON in/out) |
| `config.py` | dataclasses `Axis`, `AxesSpec`, `Candidate`, `Niche`, `SessionSettings`, `EngineConfig`; axes YAML/JSON load+validate |
| `embed.py` | pluggable embedders (`static`/`local`/`hash`/`api`) via `CAMBRIAN_EMBEDDER`; L2-normalized; near-dup `dedupe` |
| `archive.py` | MAP-Elites archive (one elite per niche) + `CVTNicher` Voronoi partition for the open axis |
| `novelty.py` | geometric novelty = mean k-NN cosine distance |
| `diversity.py` | DPP kernel + greedy MAP selection; farthest-point fallback; `bounded_quality` |
| `monitor.py` | anti-collapse monitor (entropy + mean pairwise cosine) + advisory variety-erosion sensor |
| `originality.py` | advisory distance-to-obvious-set (never in selection) |
| `gap.py` | advisory surface-vs-mechanism spread gap (never a gate) |
| `memory.py` | preference memory, ask-pair selection, diverse parent selection honoring pins/discards |
| `session.py` | per-invocation context (State + domain + AxesSpec + embedder) |
| `state.py` | file state under `~/.cambrian` (or `CAMBRIAN_HOME`); atomic writes; locks |
| `pipeline.py` | orchestration; `ingest` is the core cycle |
| `selftest.py` | hermetic e2e self-test (stubbed LLM+human) |

## C2. Embedder (I7)

- `DEFAULT_STATIC_MODEL = "minishlab/potion-multilingual-128M"` (`embed.py:39`), provider default `static` (`:38`), env `CAMBRIAN_EMBEDDER` (`:37`). model2vec `StaticModel.from_pretrained` lazily on first use (`:143-147`).
- **DISCREPANCY (precision):** "256-dim" is not a code constant — `dim` resolves lazily from the loaded model (`embed.py:146`); docstring documents 256. Hash fallback is `HASH_DIM = 512` (`:41`, sklearn `HashingVectorizer(char_wb, 2-4)`); `local` (sentence-transformers) is 384-dim. Mixed dims are rejected by `pipeline._guard_embedding_dim` (`pipeline.py:490-506`).
- Weight cache: not configured by Cambrian — delegated to model2vec/HF Hub defaults (`~/.cache/huggingface`).
- Dedup taus: `DEFAULT_DEDUP_TAU = 0.92`; per-embedder `{hash:0.92, static:0.93, local:0.94, api:0.92}` (`embed.py:48-57`).

## C3. MAP-Elites archive

- Niche id = `"axis=bucket|…"` (`archive.py:168-183`); categorical → slug, continuous → bin over `range` (default `bins=5`, `config.py:68`), open → CVT `cell<n>`.
- Elite replacement: higher fitness wins; ties → higher novelty (`archive.py:228-230`; same in `rekey_open_axis` `:276-283`).
- One elite per niche; no niche-count cap. Open axis: `OPEN_NICHES = 24` (`pipeline.py:47`), freeze at `2×24=48` accumulated mechanism embeddings (`OPEN_NICHE_FREEZE_FACTOR = 2`, `pipeline.py:53`), one-time KMeans fit then frozen + archive re-keyed (`pipeline.py:307-361`, `archive.py:239-289`).

## C4. Novelty / DPP / monitor constants

- k-NN: `k=5` (`config.py:200`, `pipeline.py:42`), cosine distance on normalized rows, reference = capped elites ∪ other survivors (self-masked); cap `novelty_ref_cap = 500` (`config.py:202`) keeping the most-novel elites.
- DPP: kernel `L = diag(q)·Gram·diag(q) + 1e-6·I` (`diversity.py:25-43`); greedy MAP (Chen 2018) with incremental Cholesky (`:49-86`); rank-deficient top-up + `LinAlgError` fallback to farthest-point sampling (`:184-202`). Pool cap `MAX_DPP_POOL = 200` (`pipeline.py:54`). Slate size from `AxesSpec.slate_size = 6`.
- Monitor (`monitor.py:30-38`): `DEFAULT_COS_THRESHOLD = 0.55`, `DEFAULT_ENTROPY_THRESHOLD = 0.50`, `DEFAULT_MARGIN = 0.15`, `DEFAULT_COS_CEILING = 0.80`, `DEFAULT_MIN_BASELINE = 2`. Trip: `too_similar (mean_cos > calibrated limit) OR too_concentrated (occupied≥3 and norm-entropy < 0.50)`; calibrated limit = `min(baseline_mean+0.15, 0.80)` after ≥2 baseline gens. Runs on RAW pre-dedup vectors (`pipeline.py:822-834`). Window `monitor_window = 5`.
- Variety erosion (advisory only): `EROSION_WINDOW=5, ACCEL_RATIO=0.5, PERSIST=2, MIN_SLOPE=0.005` (`monitor.py:45-48`).

## C5. Judge bounds (I6) — verified constants

- **Weight `0.3`**: `QUALITY_WEIGHT = 0.3` (`pipeline.py:62`), `EngineConfig.quality_weight = 0.3` (`config.py:206`).
- **Clip `[0.7, 1.3]`**: `bounded_quality(..., lo=0.7, hi=1.3)` (`diversity.py:130-131,150`) — affine rescale, damp toward uniform by weight, clip.
- Fitness enters only (a) within-niche elite choice, (b) DPP quality via `bounded_quality`. Never novelty. Drift-guarded by donor test `test_engine_config.py::test_defaults_match_module_constants`.
- Prefilter guard: `under_generation` advisory flag when submitted < `0.6 ×` `candidates_per_generation` (`under_generation_ratio = 0.6`, `config.py:220`; `pipeline.py:845-857`).

## C6. Cliché / originality / gap

- `originality_scores` = `clip(1 − max cos-sim to obvious set, 0, 2)` per idea + slate mean (`originality.py:26-58`); advisory only.
- Obvious set is built live by the skill per brief (~6 answers; first ~3 = O_train generate-away set, last ~3 = held-out O_test never optimized toward) — `SKILL.md:68-82`; selftest fixture uses exactly 6 (`selftest.py:379-391`).
- Gap probe `surface_mechanism_gap` (`gap.py:31-67`), off by default (`gap_probe = False`, `config.py:242`).

## C7. Mechanisms / operators

- Mechanism tag = value of the open/`primary_novelty` axis in `descriptor` (resolver `config.py:108-117`); generating operator in `genealogy.operator_id`.
- `references/operators.md`: **14 operators** — mutation, combination, analogy, transformation, reframing, inversion, constraint, random_stimulus, biomimicry, anti_cliche + structured: scamper, morphological, triz, principle_first. (Selftest's canned set is 6.)
- Mechanism novelty: parallel mech-embedding store, advisory `mechanism_novelty` per slate item (`pipeline.py:186-203, 222-228`).

## C8. State layout (→ Burgess `.kg/diverge/`)

- Base `~/.cambrian` / `CAMBRIAN_HOME` (`state.py:41-42,75-78`); project root = `<base>/<slug>` (`:195`).
- Files: `meta.json`, `axes.json`, `archive.json`, `candidates.json`, `embeddings.json`, `mech_embeddings.json`, `open_nicher.json`, `tmp/`; per-domain `memory/<slug>/{comparisons.jsonl, pins.json, discards.json}` (`state.py:198-280`).
- Pins/discards = JSON arrays of candidate ids; mutually exclusive, latest-wins (`state.py:404-443`).
- Pruning: only when store > `state_prune_threshold = 2000` (`config.py:224`); keep = elites ∪ pins ∪ comparison ids (`pipeline.py:399-432, 915-923`).
- Project lock: atomic-mkdir `.project.lock`, timeout 10s, stale-steal 60s, best-effort (`state.py:139-187, 295-304`).

## C9. Discards = negative memory (feeds I8)

- `add_discard` → `discards.json` (`state.py:431-443`); `ingest` excludes discarded elites from the DPP slate (`pipeline.py:588-603, 811-816`); `parents` excludes them from the breeding pool (`pipeline.py:1061-1064`, `memory.py:203-234`). Pins never dropped; re-pin un-discards.

## C10. Descriptor YAML schema (→ merges into pack.yaml)

- Top-level: `domain`, `unit_of_generation`, `axes[]`, `judge_rubric`, `slate_size` (6), `candidates_per_generation` (12), optional `engine:` overrides block (`config/domains/_schema.md`).
- Axis: `name`, `type ∈ {categorical, continuous, open}`, `range` (continuous), `primary_novelty` (≤1), `bins` (default 5). Validation in `config.py:520-581`.
- Templates: `generic.yaml` (angle/scope/form/boldness/mechanism) + examples `marketing.yaml`, `product_features.yaml`, `research_hypotheses.yaml` (the last overrides `engine: {open_niches: 32, quality_weight: 0.4}`).

## C11. Selftest gates (→ Stage 3 port)

`selftest.run` (`selftest.py:499-614`), hermetic temp home, forces `hash` embedder unless `--live`; `SELFTEST_CYCLES = 2`.
- Variety gate: `mpd_beats_single_shot` (+`MARGIN_MPD=0.10`), `vendi_beats_single_shot` (+`MARGIN_VENDI=0.5`), `entropy_beats_single_shot`, `dpp_beats_first_n` (+`MARGIN_DPP=0.01`, shuffled pool, averaged over `n_seeds=3`), `null_no_regression` (eps 0.02, 50 trials), `value_elite_wins_niche` (1.2 vs 0.9 + swap flip).
- Collapse-reversal: forced-collapse gen must trip monitor; next diverse gen quiet.
- Advisory (never in `ok`): live semantic check, originality probe (held-out), monotone gap sanity.
- `ok = variety_gate ∧ collapse_reversal ∧ files_ok ∧ semantic_ok`; CLI exit 0/1.

## C12. Provisioning + deps

- `hooks/hooks.json`: one `SessionStart` → `node ${CLAUDE_PLUGIN_ROOT}/hooks/provision.mjs`, async, timeout 600.
- Chain: provision.mjs → provision.sh/.ps1 (Python ≥3.11 finder) → `bootstrap.py --background`.
- `bootstrap.py`: venv priority `--venv` → `$CAMBRIAN_VENV` → `$CLAUDE_PLUGIN_DATA/venv` → `<skill>/.venv`; lock `.cambrian-provision.lock` (mkdir, stale 30min); `install.stamp` = sha256 of schema+reqs+pyproject; pointer `engine-python.txt`; log `provision.log`; uv preferred, stdlib venv+pip fallback; verifies `import numpy, sklearn, yaml, cambrian_engine`.
- Runtime deps: `numpy>=1.26,<3`, `scikit-learn>=1.4,<2`, `pyyaml>=6,<7`, `model2vec>=0.3,<0.9`; opt-in local: `sentence-transformers>=2.7,<6`; dev: `pytest>=8,<9`. Python `>=3.11`.

## C13. Skill + manifest

- `SKILL.md` (frontmatter `name: ideate`, `allowed-tools: Bash, Read, Write`): loop = locate interpreter via `engine-python.txt` → bootstrap if missing → resolve axes (named domain | infer+confirm | generic) → generate with operators → judge prefilter → `ingest` → present slate (coords, ask_pairs, pin/discard invite) → `remember`/`parents` → react to monitor. A-vs-B answers low-weight; pins strong+durable; discards persistent.
- `references/`: `loop.md` (authoritative procedure), `judge_rubric.md` (validity-only prefilter; documents 0.3/[0.7,1.3]), `operators.md`, `axis_inference.md` (4–6 axes, exactly one open/primary).
- `plugin.json` is metadata-only (no component arrays); skill + SessionStart hook discovered by convention. No MCP server, no agents, no commands. Marketplace `sergiparpal`, source `./`.
- Donor-repo anomalies (not Cambrian's): untracked `.kg-reconcile-state.json` (ignored via `.git/info/exclude`, not `.gitignore`) and empty untracked `canon/` — Sproutgraph leftovers in the working tree; both left untouched.

---

# Part II — Sproutgraph @ `17c4066` (convergence donor)

Plugin `sproutgraph` 0.6.1; engine package `kg-engine` 0.6.1 at `scripts/kg_engine/` (20 modules, ~9.4k LoC). Python `>=3.10`. Deps: `mcp>=1.2,<2`, `pydantic>=2,<3`, `networkx>=3,<4`, `pyyaml>=6,<7`, `python-igraph>=0.11,<2`, `leidenalg>=0.10,<1`; extras `backend=[anthropic>=0.77]`, `dev=[pytest>=8]`, `lightrag=[lightrag-hku>=1.4,<2]`.

## S1. Write boundary (I2 anchor)

- `scripts/kg_engine/boundary.py` — deterministic `P_write` validator; entry `validate_payload` (`:166`), invoked by `KGEngine.kg_write` (`server.py:630`). Pydantic `EdgeIn`/`NodeIn`/`WritePayload`, all `extra="forbid"`.
- Forge guards `_apply_forge_guards` (`boundary.py:111`): a write may assert only `unverified`; claimed verdict states are DEMOTED `"forged-verdict-stripped"` (`:122-124`); claimed `authored_by=human`/`deterministic` off-lane stripped (`:131-135`).
- Lanes in `_validate_edge` (`:397`): hypothesized lane (provenance `hypothesized`) forces `span=""` (`:435`); span-present/inferred lane requires `_verify_span` (`:348`) — rejects `no-supporting-span`, `span-not-in-source`, `span-too-short` (`MIN_SPAN_CHARS = 4`, `:41`).
- Negative-memory consultation at the boundary: `_durability_quarantine` (`:376`) QUARANTINEs re-proposals colliding with known failures/verdicts (hypothesized lane checks id + reverse).
- Vocabulary enforcement: undeclared node/edge types → QUARANTINED (`:250`, `:469`). Flood cap `DEFAULT_MAX_EDGES_PER_KB = 20.0`, `MIN_EDGE_BUDGET = 64` (`:46-47`).
- Hypothesized-lane public entry: MCP tool `kg_propose` (`server.py:675`, wrapper `:1790`) — a thin wrapper over `kg_write` that forces `provenance=hypothesized` and refuses text claims.
- **DISCREPANCY (plan §2.5):** boundary lives in `boundary.py` (server only invokes it).

## S2. Verdict monopoly (I1 anchor)

- **Only** `KGEngine.kg_ground` (`server.py:716`, MCP wrapper `:1799`) sets verdict states. Exhaustive grep: the only verdict `epistemic_state` assignments are `server.py:783` (node) and `:798` (edge). (`_merge_edge_pair` `:1055` only copies a pre-existing state between two edges.)
- `VALID_VERDICTS = {grounded, rejected, failed, obsolete}` (`server.py:56`). Flow: single-writer lease → fresh read → stamp state + `verdict_by`/`verdict_at` → audit record appended BEFORE write (`GroundAuditLog.audited_write`, `:819`) → `canon.write_one`. MCP surface always passes `by="agent"` (`:1810`).
- Hypothesis promotion: `_promote_hypothesis` (`:829`) / `_promote_hypothesis_node` (`:855`) — requires `support_span` (verified via `source_set().verifies`, → `span-present`) or `support_note` (→ `inferred`); else error `hypothesis-needs-support`.
- **DISCREPANCY:** the engine does NOT re-verify spans for ordinary verdicts on span-present edges — semantic re-checking is the `kg-grounder` subagent's job; deterministic span verification happens at write time and at hypothesis promotion.

## S3. Reconciler (I2 enforcement)

- `scripts/kg_engine/reconciler.py`, class `Reconciler` (`:43`); forge predicate `_forged` (`:487`): current state ∈ GROUNDABLE_STATES ≠ baseline AND no unconsumed `kg_ground` audit record (count-based ledger defeats replay). Re-quarantine `_requarantine_forged` (`:211`): reset to `UNVERIFIED`, clear `verdict_by`/`verdict_at`, persist under lease.
- State cache `.kg-reconcile-state.json`; audit ledger `.kg-ground-audit.jsonl` + `.ckpt` sidecar.

## S4. Span staleness (R3)

- Read-only **advisory**, not a mutating queue. `_is_stale_edge` (`projector.py:730`): GROUNDED/FAILED + span-present + span no longer verifies. Persisted to SQLite `meta['stale_verdicts']`; surfaced via `kg_context.advisory.stale_verdicts` (cap 50). "NEVER mutates a verdict" (`projector.py:749`). **DISCREPANCY** vs plan's "re-grounding queue" wording.

## S5. MCP tools — exactly 20

`_register(mcp, engine)` (`server.py:1761`); `FastMCP("sproutgraph")` (`:1971`): `kg_ping, kg_scrub, kg_write, kg_propose, kg_ground, kg_rename, kg_merge, kg_metrics, kg_status, kg_generate, kg_absorption, kg_operate, query_graph, get_node, get_neighbors, shortest_path, kg_explain_path, kg_context, kg_agenda, kg_export`. Tool namespace in frontmatter: `mcp__plugin_sproutgraph_sproutgraph__<tool>` (plugin × server name). The graph query tool is `query_graph` (no tool named `kg_query` — that's the slash command).

## S6. Epistemic model (axes)

- `EpistemicState` (`model.py:45-50`): **`unverified, grounded, rejected, failed, obsolete`**. Sets: `VERDICT_STATES={grounded,rejected,failed}`, `GROUNDABLE_STATES=+obsolete`, `FAILURE_STATES={rejected,failed}` (`:68-75`).
- **DISCREPANCY (plan I-lists & Stage 4):** "hypothesized" is a **Provenance** value (`model.py:33-36`: `span-present | inferred | hypothesized`), NOT an epistemic state. Plan's "epistemic_state: hypothesized" for materialized pins maps to **`provenance: hypothesized, epistemic_state: unverified`**.
- `AuthoredBy`: `deterministic | agent | human` (`:39-42`). `Confidence`: `EXTRACTED | INFERRED | AMBIGUOUS`.
- Edge fields (`model.py:208-235`): `source, target, relation, provenance, authored_by, epistemic_state, span, source_file, confidence, confidence_score, verdict_by, verdict_at, notes, id`. **DISCREPANCY:** no `annotations` field — the plan's "pinned annotation" (Stage 4) maps to `Edge.notes` (+ session back-reference there).

## S7. Negative memory (I8 anchor)

- Inline on edges: `epistemic_state ∈ {rejected, failed}` in canon; **never pruned** (projector keeps them; `projector.py:1064` "surfaced, never pruned"). Falsification counters computed on read: `kg_context.falsification_counters.failed_or_rejected_edges` (`projector.py:1064-1070`).
- Consulted by: boundary `_durability_quarantine` (re-proposal quarantine), `generate._is_failure` (`generate.py:185`) drops candidates whose id/reverse is in failure memory, flood baseline excludes failures.

## S8. Seven generate mechanisms

- `generate.py`: `DEFAULT_SET=["bridge","seed","compression"]` (`:43`); `ALL_SET=[...7...]` (`:47`); orchestrator `run_generators` (`:594`). Entry points: `bridge:210, seed:244, compression:293, regroup:328, transplant:377, ensemble:446, periphery:488`. All emit `Candidate` (`:74`) with `provenance=hypothesized, epistemic_state=unverified`, no span.
- Surfaced via MCP tool `kg_generate` (`server.py:1331`/`1848`) returning `{candidates:[...]}` — read-only; candidates enter canon only via `kg_propose` (and `kg_operate` for §8 endo ops), driven by `/kg-generate` + `kg-generator` subagent (which deliberately has NO `kg_ground`).

## S9. Experiment harness

- Scoring: `harness.py` `ideation` (`:357`), `_score_condition` (`:287`) → diversity/novelty/utility/unsupported_rate + `_beats` verdicts; also `agreement` (Krippendorff α), `specificity`, `convergence`, `absorption`. Arms `_CANONICAL_ARMS = ("control","graph","graph+generate","rag","lightrag")` (`:342`); lightrag optional (env `KG_LIGHTRAG=1` + dep + `OPENAI_API_KEY`).
- Blind protocol lives in `commands/kg-experiment.md` + `agents/evaluator.md`: evaluator shuffles unlabeled context blocks A/B/C/D, generates one idea per (prompt × condition), de-shuffles into JSON keyed by condition.
- **DISCREPANCY (affects D1):** no integer RNG seeds — the harness convention is **12 fixed ideation prompts** (`kg-experiment.md:91-113`) + blind shuffle. Per D1 "the harness convention wins": Stage 6 will run arms over the 12-prompt convention rather than 5 RNG seeds.

## S10. pack.yaml

- Loader `pack.py`: `PackContract` (`:20`, `extra="forbid"`): `domain` (req), `version`, `node_types` (≥1), `edge_types` (≥1), `glossary`, `specificity_seeds`; types disjoint; CLI `python -m kg_engine.pack {validate|coverage}` (`:133`).
- Data `pack/pack.yaml`: domain "conceptual theory"; 6 node_types (`compression, primitive, claim, metric, operation, failure`); 10 edge_types (`grounds, attacked_by, reconciles_with, bridges, collapses_into, confounded_by, approximates, defends_against, projects, survives`); glossary 12 terms; 11 specificity_seeds.

## S11. Provisioning + launch

- `hooks/hooks.json`: `SessionStart` → `node provision.mjs` (async, 600s) + `PreToolUse` (Grep|Glob|Read) → `node precontext.mjs` (8s; injects grounded kg_context via read-only projector).
- Chain: provision.mjs (OS dispatch) → provision.sh/.ps1 (Python ≥3.10 finder) → `bootstrap.py --background`. `resolve_venv_dir` (`bootstrap.py:121`): `--venv` > `$KG_ENGINE_VENV` > `$CLAUDE_PLUGIN_DATA/.venv` > `<repo>/.venv`. uv path `uv sync --no-install-project` (`:500-515`); pip fallback stdlib venv + `pip install <repo>` (`:518-538`). Markers: `engine-python.txt`, `install.stamp`, lock `.kg-provision.lock`. `--check`, `--reconcile` modes.
- Server launch: `.mcp.json` → `node scripts/launch_server.mjs` → resolves venv python (`_engine_resolve.mjs`; pointer file first, conventional path fallback) → `spawn(py, ["-m","kg_engine.server"])` with supervision/backoff. Env: `KG_PROJECT_DIR=${CLAUDE_PROJECT_DIR}`, `KG_DATA=${CLAUDE_PLUGIN_DATA}`, `KG_PACK_PATH`, `KG_SOURCE_PATH=${user_config.source_path}`.
- Data dir: `server.resolve_data_dir()` (`server.py:142`) = `KG_DATA` else `<project>/.kg-data`; derived layer at `<data>/derived/`.

## S12. Canon + merge driver

- `canon.py` `Canon` (`:389`): one Markdown file per node at `<project>/canon/<slug>.md`; YAML frontmatter (ordered keys `id, label, node_type, file_type, provenance, authored_by, epistemic_state, created_at, updated_at, edges:`) + body. Atomic `write_one`/batch `write_nodes` with rollback; single-writer `LeaseLock` (`.kg-session-lock`).
- Semantic merge: `canonmerge.py` (`merge_nodes:93`) unions edges by id, DEMOTES cross-branch verdict disagreements to `unverified` (cannot forge). Git driver `scripts/canon_merge_driver.mjs` + `.gitattributes` `canon/*.md merge=kgcanon`.

## S13. Derived SQLite (I4 anchor)

- Sole writer: `projector.py` (`:1137`). Files `<data>/derived/graph.json` + `index.sqlite`. Schema (`_connect`, `:530-547`): **3 tables** — `meta(key,value)`, `nodes(15 structural cols)`, `edges(11 cols)` + 3 indices. **No vector/embedding tables** (I4 assertion-ready). WAL mode. `verdict_by/verdict_at` deliberately not columns.
- Readers: `kg_context`, `query_graph`, `get_node`, `get_neighbors`, `shortest_path`, `kg_agenda`, `kg_metrics` via read-only connection (`:883`).

## S14. Embeddings removal — confirmed

- No embedding/vector code path in `scripts/kg_engine/` (grep-verified; only doc comments + unrelated "script-injection vector" in export.py + isolated optional `lightrag_arm.py`). `metrics_mode`/`with_embeddings` stored and echoed by `kg_ping` only — **inert** (no consuming branch). `test_manifests.py:68-76` guards against `sqlite_vss`/`tree_sitter` reappearing.

## S15. Commands / agents / skill

- 8 commands (all present, incl. `kg-query.md`; matches `validate_plugin.REQUIRED_COMMANDS`): kg-build, kg-eval, kg-experiment, kg-generate, kg-ground, kg-perturb, kg-query, kg-view.
- 6 agents: `kg-extractor` (sonnet; Read/Grep/kg_write/kg_metrics), `kg-grounder` (opus; +kg_ground), `kg-adversarial-grounder` (opus; +kg_write/kg_ground), `kg-generator` (kg_generate/kg_context/kg_propose, NO kg_ground), `kg-annotator` (no MCP), `kg-evaluator` (Bash + kg_context/query_graph).
- Skill `skills/sproutgraph/SKILL.md` + references `contract.md` (346 ln), `tools.md` (704 ln), `pack-schema.md` (261 ln).

## S16. Rename map (sproutgraph → burgess), non-test non-docs surfaces

`.claude-plugin/plugin.json:2`; `.claude-plugin/marketplace.json:12`; `.mcp.json:3` (server key); `hooks/hooks.json:11` (statusMessage); `server.py:509` (kg_ping name), `server.py:1971` (`FastMCP("sproutgraph")`); `validate_plugin.py:18` (`PLUGIN_NAME`), `:61` (`skills/sproutgraph/SKILL.md` path); `templates/graph_html.py:23,47` (export title); `kg_engine/__init__.py:1`; `backend.py:65` (system prompt); `launch_server.mjs:225,302,327,385`; `canon_merge_driver.mjs:26,47`; `bootstrap.py:2,707,848`; `hooks/precontext.py:98`; skill dir `skills/sproutgraph/` + SKILL.md name; tool-namespace prefix `mcp__plugin_sproutgraph_sproutgraph__` → `mcp__plugin_burgess_burgess__` across ALL commands/agents frontmatter.
- Identity-hardcoding tests: `tests/test_manifests.py:156` (namespace `_NS`), `tests/test_fix_server.py:136` (cosmetic server name), `tests/test_rfix_a11.py` (via `vp.PLUGIN_NAME`).

## S17. Tests & validation

- Test command: `uv run pytest` (pytest config in pyproject: testpaths=tests, addopts=-q). Baseline 731 passed + 2 skipped (see BASELINE.md).
- Structural gate: `uv run python scripts/validate_plugin.py` + `claude plugin validate ./ --strict`.
- Local dev loading (README:125-126): `claude --plugin-dir /path/to/<checkout>`; marketplace flow `/plugin marketplace add sergiparpal/<repo>` + `/plugin install <name>@sergiparpal`.

## S18. Dev CLIs

`python -m kg_engine.pack {validate|coverage}`; `python -m kg_engine.harness {agreement|specificity|ideation|convergence}`; `python -m kg_engine.backend extract` (headless; `anthropic` extra); `python -m kg_engine.canonmerge`; `python scripts/f4_probe.py`. Engine runtime: `python -m kg_engine.server`.

---

# Consolidated discrepancy list (plan → reality)

1. Epistemic states are `unverified|grounded|rejected|failed|obsolete`; **hypothesized is a provenance**, not a state. Materialized pins (Stage 4) = `provenance: hypothesized, epistemic_state: unverified`.
2. **No `annotations` field** on Edge/Node → "pinned" marker rides `Edge.notes` + session state.
3. Engine-side span re-checking happens at write time and hypothesis promotion, not on ordinary verdict stamping (semantic re-check = grounder subagent's job).
4. R3 staleness = read-only advisory (`kg_context.advisory.stale_verdicts`), not a mutating queue.
5. Experiment harness convention = **12 fixed prompts + blind shuffle**, no RNG seeds → D1 applies the harness convention (per D1's own escape clause).
6. All 8 slash commands exist (incl. kg-query.md); the query MCP tool is `query_graph`.
7. Cambrian engine lives at `skills/ideate/scripts/cambrian_engine/`; embedder dim is a model property (hash fallback = 512-dim); judge constants 0.3 / [0.7,1.3] confirmed in code.
8. Cambrian plugin.json is metadata-only; components discovered by convention (1 skill + 1 SessionStart hook).

