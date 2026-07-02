# Attribution

Burgess is a fusion of two MIT-licensed donor plugins by the same author. Both donors continue to exist as independent projects; code was **copied** (vendored) at the pinned SHAs below, never moved or modified upstream.

| Donor | URL @ SHA | License |
|---|---|---|
| Sproutgraph (convergence spine) | https://github.com/sergiparpal/Sproutgraph @ `17c406632bb547a4abca3a824d9ffdc577e83891` | MIT (Copyright (c) 2026 Sergi Parpal) |
| Cambrian (divergence engine) | https://github.com/sergiparpal/Cambrian @ `a2adfa1d8b83c52ba17a79382811ea82012f8f99` | MIT (Copyright (c) 2026 sergiparpal) |

## Ported areas

### Stage 1 — Sproutgraph foundation (all from Sproutgraph @ `17c4066`, copied via `git archive`)

| Burgess path | Donor path | Adaptations |
|---|---|---|
| `scripts/kg_engine/**` (20 modules + templates) | `scripts/kg_engine/**` | identity strings only (`sproutgraph→burgess` in `__init__.py` docstring, `server.py` kg_ping name + `FastMCP("burgess")`, `backend.py` system prompt, `templates/graph_html.py` titles); `__version__` 0.6.1→0.1.0 |
| `scripts/{bootstrap.py, launch_server.mjs, _engine_resolve.mjs, canon_merge_driver.mjs, validate_plugin.py, f4_probe.py}` | same paths | identity strings (`[burgess]` log prefixes, `PLUGIN_NAME="burgess"`, `skills/burgess/SKILL.md` required path) |
| `commands/*.md` (8) | `commands/*.md` | tool-namespace prefix `mcp__plugin_sproutgraph_sproutgraph__` → `mcp__plugin_burgess_burgess__`; prose identity |
| `agents/*.md` (6) | `agents/*.md` | same namespace + prose identity |
| `hooks/{hooks.json, provision.mjs, provision.sh, provision.ps1, precontext.mjs, precontext.py}` | same paths | statusMessage + injected-context header identity |
| `skills/burgess/**` | `skills/sproutgraph/**` | directory + skill `name:` renamed; namespace prefix; prose identity |
| `pack/{pack.yaml, glossary.md}` | same paths | none |
| `tests/**` (51 files) | `tests/**` | identity strings only: `test_manifests.py` `_NS` namespace prefix; `test_fix_server.py` test-server name; no logic/count changes — suite green at baseline parity (731 passed, 2 skipped) |
| `.mcp.json` | `.mcp.json` | server key `sproutgraph→burgess` |
| `.claude-plugin/{plugin.json, marketplace.json}` | same paths | name `burgess`, version `0.1.0`, fused description; userConfig schema unchanged |
| `pyproject.toml` | `pyproject.toml` | version 0.1.0, description identity; package name `kg-engine` and all dependency pins unchanged |
| `.gitattributes`, `.github/workflows/ci.yml`, `examples/source.md` | same paths | `.gitattributes` merge-driver name unchanged (`kgcanon`); CI identical (it is donor-agnostic) |

Not vendored (donor-specific): `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `PROGRESS.md`, `images/`, `LICENSE` (Burgess has its own MIT), `.claude/settings.local.json` (untracked donor-local), `uv.lock` (untracked in donor by design — generated per machine).
