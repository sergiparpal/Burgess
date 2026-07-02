# Decisions Log

Every kickoff answer, every default applied on timeout, every judgment call. One-line rationale each.

## Kickoff questionnaire (2026-07-02, answered live by user via AskUserQuestion)

- **Q1 Plugin name = `Burgess`** — user selected the recommended option; matches the pre-existing repo/GitHub name. (Burgess Shale: where the Cambrian explosion's forms were preserved — divergence + grounding in one word.)
- **Q2 Command prefix = keep `/kg-*`** — user selected recommended; continuity for donor users.
- **Q3 Divergence command = `/kg-diverge`** — **user's active choice over the recommended `/kg-ideate`.** Applied consistently: command file `commands/kg-diverge.md`; project-local session state under `.kg/diverge/<brief-slug>/`. Wherever FUSION_PLAN.md says `/kg-ideate` or `.kg/ideate/`, read `/kg-diverge` and `.kg/diverge/`.
- **Q4 Dev CLI = yes** — keep `python -m kg_engine.divergence`; zero-cost, aids debugging, lets the divergence selftest run outside MCP.
- **Q5 Materialization = explicit action** — user selected recommended; nothing enters the graph implicitly.
- **Q6 First version = `0.1.0`** — user selected recommended; honest maturity signal.

## Stage 0 judgment calls

- **Deleted stray `FUSION_PLAN.md:Zone.Identifier`** (WSL/NTFS download-zone metadata artifact, 25 bytes, not project content) and gitignored the pattern.
- **Baseline method:** donor suites run on pristine `git archive HEAD` copies inside the session scratchpad — donor trees never executed in (I11). Sproutgraph's `pyproject.toml` already sets `addopts = "-q"`; adding another `-q` yields `-qq` which suppresses the pytest summary line, so the canonical baseline invocation is `uv run --extra dev pytest tests/ -p no:cacheprovider` (single `-q` effective).
- **I11 gate implementation:** cross-platform Python script `scripts/check_donors_clean.py` reading pins from `scripts/donor_pins.json`; installed locally as `.git/hooks/pre-commit` (hook is local-only by git design; the script itself is committed and must be run before every stage commit per protocol §6.4).

## Inventory-driven adaptations (D2: code wins over plan prose)

- **"Hypothesized" is a provenance, not an epistemic state** (model.py:33-50). Everywhere the plan says materialized pins get `epistemic_state: hypothesized`, Burgess implements `provenance: hypothesized, epistemic_state: unverified` — the donor's actual hypothesized lane.
- **No `annotations` field exists on Edge/Node.** The Stage-4 "pinned annotation" rides `Edge.notes` (plus the diverge-session back-reference), per INVENTORY discrepancy 2.
- **D1 uses the harness's own convention** (per D1's escape clause): the vendored experiment harness defines no RNG seeds — its convention is 12 fixed ideation prompts + blind shuffle/de-shuffle by the evaluator. Stage 6 measures arms over that convention; the D1 thresholds (median comparison, win-rate, noise band) apply over the 12 prompts.
- **Materialization front door:** the donor's hypothesized-lane public entry is `kg_propose` (a thin forced-provenance wrapper over `kg_write`, server.py:675). Stage-4 materialization goes through the propose lane — this **is** the "via kg_write exclusively" requirement in donor terms.

## Stage 1 judgment calls

- **"Loads locally in Claude Code" verified deterministically:** `claude plugin validate ./ --strict` (the CLI's own loadability gate) + a real MCP stdio handshake through the plugin's actual launch chain (`node scripts/launch_server.mjs` with the `.mcp.json` env contract): initialize → serverInfo.name=`burgess` → tools/list = 20 tools → `kg_ping` returns name=burgess v0.1.0. An interactive `claude --plugin-dir` session is listed in the final human handoff (it requires the `source_path` userConfig prompt, which is inherently interactive).
- **Vendored donor CI workflow** (`.github/workflows/ci.yml`) — two vendored tests require it (`test_ci_matrix_covers_windows_and_macos`, `test_ci_test_job_sets_up_node`) and it is donor-agnostic. Keeping it preserves baseline parity without test adaptations.
- **Engine pip-package name `kg-engine` kept** (not donor identity — it names the `/kg-*` engine); description + versions updated to Burgess 0.1.0 (validate_plugin enforces plugin.json ↔ `kg_engine.__version__` agreement, which caught the initial miss).
- **uv.lock not committed** — donor convention (gitignored; provisioning locks per machine); Burgess follows it.

## Stage 2 judgment calls

- **Whole-engine port at Stage 2** (all 15 Cambrian modules incl. state/pipeline/selftest, not just the math listed in the stage's task): porting the full package + its 226 tests front-loads the port risk into the stage whose firewall tests exist for exactly that; Stage 3 builds only the command/skill layer on top.
- **Env identity surface renamed like Stage 1's:** `CAMBRIAN_EMBEDDER/HOME/DEBUG/EMBED_API*` → `KG_DIVERGE_*`. Constants untouched (I6/I7, D2).
- **Session semantics (I10):** session boundary = `init-project`'s `session` id. Omitted id ⇒ fresh auto id ⇒ geometry wiped (ephemeral by default); passing the persisted id ⇒ resume. The /kg-diverge command (Stage 3) passes one id per chat session. Durable across sessions: pins, discards, comparisons, axes snapshot, project meta identity, session.json. Ephemeral: archive, candidates, embeddings, mech_embeddings, open_nicher + geometry-coupled meta series (cycles, cos_window, novelty_window, erosion_streak, gap_log).
- **Divergence deps are core deps with lazy guarded imports** (plan Stage 2 task 3): installed by default so /kg-diverge works out of the box; I9 enforced by guarded imports + actionable errors + `test_core_engine_works_with_divergence_deps_blocked` (full write→ground→query round-trip in a process where numpy/sklearn/model2vec imports are blocked).
- **Domain templates live at `pack/domains/`** (pack fragments per plan §3.2/Stage 3); resolver prefers `KG_PACK_PATH/../domains` so wheel installs work, falls back to the repo layout for dev/tests.
- **Divergence engine version = 0.1.0** (`kg_engine.divergence.__version__`) — it is Burgess's component now; lineage recorded here and in ATTRIBUTION.md.
