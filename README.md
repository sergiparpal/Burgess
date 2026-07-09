# Burgess

![burgess-with-fossils.png](images/burgess-with-fossils.png)

**The full creative cycle in one Claude Code plugin: diverge without collapsing to the mean, converge without believing your own ideas.**

> 📖 **New to Burgess?** Start with the tutorial — a plain-language guide for non-technical users through one full creative cycle, from a blank page to a grounded knowledge graph. No programming required.
>
> Sergi Parpal. *A Complete Walkthrough — from a Blank Page to Grounded Knowledge* (Burgess tutorial). [`TUTORIAL.md`](TUTORIAL.md).

Burgess fuses two engines around one boundary:

- a **convergence engine** (from Sproutgraph) that grows source documents into a rigorously grounded, queryable knowledge graph — human-editable canon, three-axis provenance, a span-present write boundary, a grounding loop with permanent memory of failures, and a regenerable NetworkX/SQLite derived layer;
- a **divergence engine** (from Cambrian) that turns any brief into a diverse, non-cliché slate of ideas — a local, server-less MAP-Elites archive with k-NN geometric novelty, DPP slate selection, and an anti-collapse monitor, with you steering and selecting in chat.

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

## Configuration

Installing Burgess asks for **four settings**. Only the first is required; the other three ship with working defaults you can ignore until you have a reason not to. Claude Code prompts for them at install time and stores them per-installation — to change one later, reconfigure the plugin from the `/plugin` interface. The engine reads its settings when the MCP server starts, so a changed value takes effect on the next session.

| Setting | Required | Values | Default | What it controls |
| --- | --- | --- | --- | --- |
| `source_path` | **Yes** | a file, a directory, or a glob | — | The document(s) your graph is built and grounded against |
| `sensitivity` | No | `low` · `medium` · `high` | `medium` | How aggressively text is scrubbed before it leaves for a subagent |
| `metrics_mode` | No | `structure_only` · `with_embeddings` | `structure_only` | Which signal the graph's metrics use |
| `extract_wave_size` | No | `1`–`10` | `6` | How many extractors `/kg-build` runs concurrently |

### `source_path` — the document your graph is grounded against *(required)*

The one setting Burgess cannot run without, because it names the source of truth. Every non-deterministic edge in the graph must quote a **verbatim span** from one of these files, and `/kg-ground` re-checks each span against the specific file it came from. This is what lets the plugin tell you a claim is *supported* rather than merely plausible. The `burgess` MCP server does not start until it is set.

| Form you enter | Resolves to | Notes |
| --- | --- | --- |
| A single **file** | Just that file | Any extension — you pointed at it directly, so it is honored even if it isn't `.md`/`.txt` |
| A **directory** | Every `.md`/`.txt` directly inside it | **Not recursive.** Dotfiles are skipped |
| A **glob** | Every matching `.md`/`.txt` | Use a `**` segment to recurse into subdirectories |

```text
/home/me/notes/theory-of-change.md      a single document
C:\docs\source.md                       the same, on Windows
/home/me/research/papers                every .md/.txt directly in that folder
/home/me/research/**/*.md               every .md at any depth below it
```

Four rules worth knowing before you type it:

- **Enter the bare path, without surrounding quotes** — `C:\docs\source.md`, not `"C:\docs\source.md"`. Quotes are stripped defensively, but don't add them.
- **Markdown and plain text only.** No PDFs, no media.
- **Files are deduped by basename.** If a directory or glob resolves two files both named `notes.md`, only one is used — the lexicographically-first full path, so the choice is stable across machines. Rename one if you need both.
- **A non-UTF-8 or binary file in the resolved set is skipped**, not fatal; the rest of the build proceeds.

`/kg-build` resolves this value **through the engine**, never through a shell variable. That is deliberate: a configured source can never be silently ignored, and an unreadable path stops the build with a message rather than quietly falling back to the bundled demo corpus.

### `sensitivity` — how much is redacted before text leaves your machine

When `/kg-build` hands a section of your source to an extractor subagent, that text crosses an **egress boundary**. It is scrubbed first: secrets and PII are replaced with *consistent* placeholders (`⟦SECRET:1⟧`, `⟦EMAIL:1⟧`, …) so the relational structure survives the redaction while the sensitive values do not leave. Spans are restored to their original text when written to the canon — **the scrub protects the egress, not your local graph.**

| Value | Redacts | Choose it when |
| --- | --- | --- |
| `low` | Secrets only — API keys, tokens, credentials | The document is public or already clean, and you want spans to read exactly as written |
| **`medium`** *(default)* | Secrets **+ structured PII**: emails, phone numbers, SSNs, credit-card numbers, IP addresses, credentialed URLs | Almost always. Structured PII is matched by shape, so false positives are rare |
| `high` | Everything in `medium` **+ person-name and street-address heuristics** | The document names people or addresses you don't want leaving your machine |

**Secrets are always scrubbed, at every level** — `low` does not mean off. An unrecognized value falls back to `medium`.

`high` uses heuristics rather than exact patterns, so it redacts more aggressively and can catch ordinary capitalized phrases. If spans start reading as `⟦PERSON:1⟧` where no person exists, step back to `medium`.

This setting also governs engine **error text**: absolute filesystem paths are always redacted, and the same secret/PII scrub runs on top before an error reaches your transcript.

### `metrics_mode` — which signal the graph's metrics use

| Value | Effect |
| --- | --- |
| **`structure_only`** *(default)* | Graph structure is the signal: degree, betweenness, communities, the specificity gate. This is the mode that does something. |
| `with_embeddings` | **Currently inert.** The embedding-backed candidate generator it once selected (sqlite-vss) was removed; the option is kept for compatibility. Selecting it changes nothing. |

Leave it at `structure_only`. It is documented here only because you will see it in the install prompt and in `kg_ping`'s output, and a setting that looks meaningful but isn't deserves to be named as such. An unrecognized value falls back to `structure_only`.

This has **no bearing on `/kg-diverge`**, whose embedder is always model2vec. `metrics_mode` governs the knowledge graph's metrics, nothing else.

### `extract_wave_size` — how many extractors `/kg-build` runs at once

`/kg-build` launches **one extractor subagent per section**, and that isolation is load-bearing: an extractor can only copy a span verbatim from text it can actually see, which is what makes `span-present` checkable rather than remembered. This setting changes only how many of those single-section extractors run **concurrently**, in bounded waves.

| Value | Effect |
| --- | --- |
| `1`–`2` | Effectively serial. Gentlest on rate limits; lets you watch each section land |
| **`6`** *(default)* | A 19-section document builds in four waves (6 + 6 + 6 + 1) |
| `8`–`10` | Fastest on a long document; expect rate-limit and lock pressure |

Unlike the three above, this is an **orchestration knob** the `/kg-build` command reads — the engine never sees it. So `/kg-build`'s own second argument overrides it for a single run:

```text
/kg-build notes/theory-of-change.md 2     this run uses a wave of 2, whatever the setting says
```

Values are clamped to `1`–`10`. Non-numeric, or below `1`, falls back to `6`; above `10` clamps to `10`.

### Verifying your configuration

The status tools have no slash — just ask Claude in plain words:

```text
"Is the Burgess engine running?"    → kg_ping reports version, sensitivity, metrics_mode
"What source is configured?"        → kg_status reports the resolved source path and its files
```

If `kg_status` reports no source, `/kg-build` will stop and tell you rather than build the wrong thing.

## Quick start

Installed? This is the whole everyday flow — the commands you'll actually type, in the order you'd reach for them. Run each in Claude Code and steer the rest in plain chat; skip any phase you don't need.

`/kg-diverge` → `/kg-build` → `/kg-ground` → `/kg-generate` → `/kg-query` · `/kg-view`

1. **Brainstorm** *(optional)* — `/kg-diverge <brief>` opens a wide, non-cliché idea slate. **Pin** the keepers in chat, then ask Claude to *materialize* them into the graph as hypotheses. No document required — this half stands alone.
2. **Build** — `/kg-build <file / folder / glob>` turns your source into a span-anchored graph; everything starts **unverified**. It's additive — run it again with another document to grow the same graph.
3. **Verify** — `/kg-ground` is the **only** command that can mark anything trusted: it confirms each relationship against a verbatim span in your source. Whatever fails becomes permanent negative memory and is never re-proposed.
4. **Expand** *(optional)* — `/kg-generate` lets the graph's own structure propose fresh hypotheses (unlinked pairs, neglected concepts, …). Generation never filters — run `/kg-ground` again to judge the new candidates.
5. **Use** — `/kg-query <question>` answers from the grounded graph with trust levels and provenance attached; `/kg-view` renders an offline `graph.html` + `GRAPH_REPORT.md`.

If you just have a document and a question, that's a three-command first session:

```text
/kg-build notes/*.md      # build a graph from your source(s)
/kg-ground                # fact-check it against that source
/kg-query "<question>"    # ask it — answers carry their provenance
```

Prefer it in plain language, nothing assumed? The full walkthrough is [`TUTORIAL.md`](TUTORIAL.md); every command's exact arguments are in the [cheat sheet](#command-cheat-sheet) below.

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
      │                    citation); failures are PERMANENT negative memory. A FALSIFIED pin
      │                    flows back into the brief's discards; a merely-unsupported novel pin
      │                    waits in the lane, recoverable, until you add sources
      ▼
/kg-generate               seven structural mechanisms propose from the graph itself; with
                           divergence.dpp on, the same slate is presented in advisory-DPP order
                           with geometry labels (measured blind; see docs/fusion/EXPERIMENT.md)
```

Plus everything the convergence side always did: `/kg-build`, `/kg-query`, `/kg-eval`, `/kg-experiment` (now with a `graph+generate+dpp` arm), `/kg-perturb`, `/kg-view`.

## Command cheat sheet

Every slash command, with its arguments. The everyday flow is **diverge → build → ground → generate → query → view**; `/kg-perturb`, `/kg-eval`, and `/kg-experiment` are the optional "going further" commands. Arguments in `<angle brackets>` are **required**; those in `[square brackets]` are **optional** and fall back to a sensible default.

This table is the summary. The full **[command manual](docs/COMMANDS.md)** documents what every argument option means and gives worked examples for each case.

| Command | What it does | The detail in brackets |
| --- | --- | --- |
| `/kg-diverge <brief> [domain-template] [reach]` | Diverge from a brief into a non-cliché slate; pin/discard in chat; optionally materialize the pins — no graph or source needed | **Required:** your creative brief. *Optional:* a domain template to steer the mechanisms; a `reach` dial — `conservative\|balanced\|wild` (default `balanced`) — capping how far out the slate goes in *degree*, never in *kind* |
| `/kg-build [source_path] [wave_size]` | Extract a span-anchored graph from your source (wave-parallel extractors); additive to any existing graph | *Optional:* the document / folder / glob to build from (defaults to your `source_path` config); how many sections per parallel wave |
| `/kg-ground [query-or-node-filter]` | Run the grounding loop — the **only** verdict path: promotions need support, failures become permanent memory | *Optional:* limit it to one topic or node area (defaults to the whole backlog) |
| `/kg-generate [mechanism-set] [k]` | Propose hypothesized candidates from graph structure (7 mechanisms; optional advisory-DPP order) | *Optional:* which mechanism(s) — `bridge\|seed\|compression\|regroup\|transplant\|ensemble\|periphery`; how many candidates |
| `/kg-perturb [second_source_or_graph_json]` | Build a second, independent construction and cross-generate to surface bridges your own view would resist | *Optional:* a second document or `graph.json` (defaults to a re-angle of the same source) |
| `/kg-query <question>` | Answer from the grounded graph, with provenance and falsification counters attached | **Required:** your question |
| `/kg-view [html\|report\|all]` | Render the offline `graph.html` + `GRAPH_REPORT.md`; read-only — it never changes the graph | *Optional:* which artifact to render (defaults to both) |
| `/kg-eval [graph.json]` | Measure extractor precision (Stage 4) and grounding reliability (Stage 7) | *Optional:* which `graph.json` to grade (defaults to the current derived graph) |
| `/kg-experiment [prompts_path]` | Blind multi-arm ideation experiment (control / graph / graph+generate / graph+generate+dpp / rag) | *Optional:* a file of test prompts (defaults to the built-in set) |

Remember: the status check (`kg_ping`) and the other behind-the-scenes MCP tools have **no** slash — just ask Claude for them in plain words.

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
The suite currently reports: **1184 passed, 2 skipped** (`uv run --extra dev pytest tests/`).
<!-- test-count:end -->

This line is generated from pytest output, never hand-written. Run it yourself:

```bash
uv sync --extra dev   # or: pip install -e ".[dev]"
uv run pytest tests/
```

The fusion invariants live in `tests/fusion/` (import firewall, DB isolation, adversarial forge attempts, graceful degradation, archive ephemerality, snapshot invariance, verdict neutrality); the divergence engine's ported suite in `tests/fusion/divergence/`; the vendored convergence suite at `tests/`.

## Lineage

Burgess is a fusion of two MIT-licensed plugins by the same author. Both donor repositories have since been
retired and are no longer published; Burgess is their continuation:

- **Sproutgraph** — the convergence spine (engine, MCP boundary, commands, agents, experiment harness, canon/derived model), vendored at `17c4066`.
- **Cambrian** — the divergence engine (embedder, MAP-Elites, novelty, DPP, monitor, judge bounds, cliché discipline), vendored at `a2adfa1`.

Per-file attribution with SHAs and every adaptation: [`docs/fusion/ATTRIBUTION.md`](docs/fusion/ATTRIBUTION.md). Migrating from either donor: [`docs/MIGRATION.md`](docs/MIGRATION.md). How this plugin was built (the full fusion plan and its decision log): [`docs/fusion/`](docs/fusion/).

## License

MIT — see [LICENSE](LICENSE).
