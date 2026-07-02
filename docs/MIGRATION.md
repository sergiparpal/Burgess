# Migrating to Burgess

Burgess vendors both donors at pinned SHAs (Sproutgraph @ `17c4066`, Cambrian @
`a2adfa1`); the donors continue as independent projects. This guide maps what
you had to what Burgess does.

## From Sproutgraph

Burgess **is** Sproutgraph at baseline parity, plus the divergence side. Nothing
you know changes:

- **Commands:** all eight `/kg-*` commands keep their names and semantics
  (`/kg-build`, `/kg-ground`, `/kg-query`, `/kg-eval`, `/kg-experiment`,
  `/kg-generate`, `/kg-perturb`, `/kg-view`). New: `/kg-diverge`.
- **Data:** the canon (`canon/*.md`), derived layer, audit ledger, reconcile
  state, and pack format are unchanged — an existing Sproutgraph project
  directory works as-is. The plugin/server identity is `burgess` (tool
  namespace `mcp__plugin_burgess_burgess__*`), and the plugin data dir is
  Burgess's own (a fresh venv provisions on first load).
- **pack.yaml:** unchanged schema, plus an OPTIONAL `divergence:` section
  (behavior axes for /kg-diverge + the `dpp` flag). Packs without it work
  untouched.
- **/kg-experiment:** the four donor arms are unchanged; a fifth
  `graph+generate+dpp` arm measures the advisory-DPP presentation.
- **New, opt-in:** `divergence.dpp: true` in the pack (or `dpp: true` per
  `kg_generate` call) presents generate slates in advisory-DPP order with
  geometry labels. Grounding behavior is bit-identical either way
  (snapshot-tested).

Uninstall/disable the Sproutgraph plugin before enabling Burgess in the same
project — they register the same `/kg-*` command names.

## From Cambrian

The engine, constants, and loop semantics are preserved; the packaging moved
into the graph plugin's trust boundary:

| Cambrian | Burgess |
|---|---|
| `/cambrian:ideate <brief>` | `/kg-diverge <brief>` |
| Skill drives a local CLI (`python -m cambrian_engine …` + tmp-file hand-offs) | Command drives MCP tools (`kg_diverge_init/ingest/remember/parents/metrics/recall/materialize`) — JSON in, JSON out |
| State in `~/.cambrian/<project>/` | Project-local `.kg/diverge/<brief-slug>/` (git-friendly) |
| MAP-Elites archive persists across sessions | **Session-ephemeral** (I10): a new session wipes the geometry archive; pins, discards and comparisons persist. The knowledge graph is the durable archive — pin what matters, materialize it. |
| `CAMBRIAN_EMBEDDER` / `CAMBRIAN_HOME` / `CAMBRIAN_DEBUG` | `KG_DIVERGE_EMBEDDER` / `KG_DIVERGE_HOME` / `KG_DIVERGE_DEBUG` |
| Domain configs `config/domains/*.yaml` | Pack fragments `pack/domains/*.yaml` (same schema), or a `divergence:` section inside `pack.yaml` |
| `python -m cambrian_engine selftest` | `python -m kg_engine.divergence selftest` (same gates, same margins) |
| — | New: pinned ideas can **materialize** into the graph's hypothesized lane and earn grounding (or permanent falsification, which auto-discards them from the brief) |

**Preference memory importer** (one-shot, read-only on the source):

```bash
python -m kg_engine.divergence import-cambrian --project <brief-slug> \
    [--from ~/.cambrian/<old-project>]
```

Pins, discards, and A-vs-B comparisons are mapped per domain into
`.kg/diverge/<brief-slug>/memory/`. Geometry files (`archive.json`,
embeddings, open-nicher) are deliberately NOT imported — session-ephemeral by
design — and `meta.json`/`axes.json` are re-created by `kg_diverge_init`; the
importer reports both as `skipped` so nothing disappears silently.

Judge bounds (weight 0.3, fitness clip [0.7, 1.3]), monitor thresholds
(0.55 / 0.50 / +0.15 ceiling 0.80), k-NN k=5, DPP pool cap 200, open-axis
niching 24×2, dedup taus, and the embedder id are the donor's constants,
verbatim, drift-guarded by tests.
