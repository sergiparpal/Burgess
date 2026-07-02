# EXPERIMENT.md — divergence.dpp default decision (FUSION_PLAN Stage 6, Decision Rule D1)

## Pre-declared protocol (written BEFORE any results were generated)

**Question.** Does presenting /kg-generate's hypothesized slate in advisory-DPP order with
geometry labels (`graph+generate+dpp`) lift blind ideation over the identical slate in donor
(score-ranked) order (`graph+generate`)? The candidate SET is identical by construction
(I5, snapshot-enforced) — only presentation differs.

**Harness convention (D1's escape clause).** The vendored harness defines no RNG seeds; its
convention is the **12 fixed ideation prompts** of `commands/kg-experiment.md` plus a blind
shuffle/de-shuffle protocol, scored deterministically by `kg_engine.harness.ideation`
(diversity, novelty, utility, unsupported_rate — n-gram measures vs the corpus). The
harness convention therefore replaces "N = 5 seeds" with **N = 12 prompts**; D1's per-seed
criteria map to per-prompt criteria, declared here before the run:

- **Per-prompt blind score** (the harness defines no single scalar, so one is pre-declared —
  the equal-weight, sign-corrected composite of the harness's four axes, each already in [0,1]):
  `score = diversity + novelty + utility − unsupported_rate`.
- **Flip `divergence.dpp` default to ON iff ALL of:**
  1. median per-prompt score(dpp arm) **strictly exceeds** median(baseline arm);
  2. the dpp arm **wins ≥ 10 of 12 prompts** (the nearest integer ≥ D1's 4-of-5 = 80% win rate);
  3. **no prompt regresses** by more than the noise band = **5% of the baseline median**
     (the harness defines no noise band, so D1's fallback applies).
- Otherwise the default **stays OFF** — and this file says so plainly. Either outcome ships:
  the structural fusion is complete regardless; only the flag's default is being decided.
- The pooled `harness ideation` table and its `dpp_verdict` are reported alongside as the
  harness's own read; the pre-declared rule above is what decides the flag.

**Setup.**
- Corpus: `examples/source.md` (the shipped standard demo corpus), verbatim.
- Graph: built by the executing agent as extractor — span-present edges written via `kg_write`
  (every span a verbatim source substring, boundary-verified), a majority grounded via
  `kg_ground`, two proposals actively FAILED so negative memory is populated, a couple left
  unverified. Exact counts in Results.
- Slates: one `kg_generate(mechanism="all", k=12, dpp=false)` and the same with `dpp=true`
  (identical sets asserted; only order/labels differ).
- Context packs per prompt: `kg_context(query=<prompt>, budget=2000)` grounded items rendered
  as opaque text; the arm block appends the slate — donor order for the baseline arm,
  advisory-DPP order + labels (bin, semantic novelty, cliché distance) for the dpp arm.
- Blinding: per prompt, the two blocks are shuffled with a seeded RNG (seed 7) and presented
  to a fresh generator subagent as "Context X / Context Y" — the generator never sees arm
  names, and the orchestrating script holds the mapping until de-shuffle. One idea
  (2–4 sentences) per (prompt × block).
- Wall-time cap: 60 minutes (D1); this run is far under it.

## Results (run 2026-07-02; wall time ≈ 4 minutes, far under the 60-minute cap)

**Graph built:** 33 items accepted from `examples/source.md` (12 span-present edges + their
nodes), 8 edges grounded, 2 proposals actively failed (negative memory populated), 2 left
unverified. **Slates:** `kg_generate(mechanism="all", k=12)` → 18 candidates, identical sets
flag off vs on (asserted); dpp advisory applied. **Blinding:** 12 fresh generator subagents,
one per prompt, seeded shuffle (seed 7; X held the dpp block in 8/12 prompts); no agent saw
an arm name; the mapping file stayed outside the blind task directory.

### Pooled harness table (`kg_engine.harness.ideation`)

| arm | n | diversity | novelty | utility | unsupported_rate |
|---|---|---|---|---|---|
| graph+generate | 12 | 0.970 | 0.946 | 0.533 | 0.160 |
| graph+generate+dpp | 12 | 0.964 | 0.961 | 0.433 | **0.347** |

Harness `dpp_verdict`: **"graph+generate+dpp did NOT clearly beat graph+generate"**
(novelty up slightly, but diversity and utility down and unsupported_rate more than
doubled — far beyond the 0.05 slack).

### Pre-declared per-prompt D1 rule

Per-prompt scalar (`diversity + novelty + utility − unsupported_rate`, declared above):

| | p0 | p1 | p2 | p3 | p4 | p5 | p6 | p7 | p8 | p9 | p10 | p11 | median |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 2.646 | 2.055 | 2.230 | 2.330 | 2.013 | 2.256 | 2.698 | 2.190 | 1.946 | 2.349 | 2.938 | 2.181 | **2.243** |
| dpp | 1.523 | 2.667 | 2.256 | 2.000 | 1.516 | 2.153 | 2.193 | 2.183 | 1.640 | 1.672 | 2.500 | 2.257 | **2.168** |

1. median(dpp) = 2.168 does **NOT** strictly exceed median(baseline) = 2.243 → criterion 1 fails.
2. dpp wins **3 / 12** prompts (needed ≥ 10) → criterion 2 fails.
3. Noise band = 5% × 2.243 = 0.112; prompts regressing beyond it: **7** (p0, p3, p4, p6, p8, p9, p10) → criterion 3 fails.

### Outcome

**All three D1 criteria fail → `divergence.dpp` default stays OFF.** The shipped
`pack/pack.yaml` keeps `dpp: false`; the arm, the flag, and the per-call override ship
regardless — only the default was being decided, and the measurement said no.

**Observed mechanism (honest read, not part of the rule):** the dpp arm's geometry labels
(niche bins, `semantic_novelty`, `cliche_distance` values) leaked into the generated ideas
as apparatus-jargon — several dpp-arm ideas cite the numbers themselves ("uniformly low
semantic_novelty (about 0.18-0.25)…"), which the harness correctly scores as unsupported
(those terms never appear in the source). The advisory ORDER may well be harmless-to-useful;
rendering the raw label VALUES into the generator's context measurably hurt. A future
refinement (out of scope for 0.1.0, noted in BLOCKERS.md as FUTURE): present geometry labels
to the human only, or strip numeric values from the generator-facing block — then re-run D1.
