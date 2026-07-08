"""Key-free, in-session SECOND CONSTRUCTION for /kg-perturb (§9/§15).

The exo move needs a *second graph construction* to cross-generate against. The only builder used to
be the headless backend (`python -m kg_engine.backend extract`), which requires the `anthropic` SDK +
`ANTHROPIC_API_KEY` — so `/kg-perturb` was the one command that could not run in a stock install.

The fix (perturb-keyfree-second-construction.md, Approach A) routes the SAME key-free, span-verified
in-session write path (`kg_write`/`kg_propose`) to a separately-NAMED alternate canon under
`<project>/.kg/constructions/<slug>/`, mirroring `divergence/state.py`'s per-name store rule. A
`kg-extractor` subagent can then build the second construction with no API key, and
`kg_generate(second_construction=<name>)` projects it and cross-generates.

These tests pin: (a) a `construction=` write lands in the alt canon and NOT the primary; (b) the
primary canon is byte-for-byte unchanged by a construction write (the `construction=None` default is
untouched); (c) `kg_generate(second_construction=…)` emits real `perturbation=external` candidates
with NO `regroup` degrade note; (d) an absent/empty construction degrades to `regroup` (never crashes,
never silently cross-generates against nothing).
"""
from __future__ import annotations

from pathlib import Path

import pytest


# Two primary edges whose spans are verbatim substrings of the conftest SOURCE. They put `degree` and
# `betweenness` in the primary graph but leave them NON-adjacent (degree–importance and
# betweenness–generality-confound are the only adjacencies) — so a `degree ⇄ betweenness` bridge that
# exists in a SECOND construction is genuinely "external structure our own dynamics resisted".
def _primary_two_edges(engine) -> dict:
    return engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "provenance": "span-present", "authored_by": "agent", "epistemic_state": "unverified",
         "span": "Degree approximates importance", "source_file": "source.md"},
        {"source": "betweenness", "target": "generality-confound", "relation": "confounded_by",
         "provenance": "span-present", "authored_by": "agent", "epistemic_state": "unverified",
         "span": "Betweenness is confounded by the generality confound", "source_file": "source.md"}]})


def _second_source(vault: Path) -> Path:
    p = vault / "second.md"
    p.write_text("Degree bridges betweenness in the alternate construction.\n", encoding="utf-8")
    return p


def _build_second_construction(engine, vault: Path, *, name: str = "t2") -> dict:
    """Build a one-edge `degree bridges betweenness` construction, span-verified against its OWN source."""
    second_src = _second_source(vault)
    return engine.kg_write({"nodes": [
        {"id": "degree", "label": "Degree", "node_type": "metric", "provenance": "span-present",
         "authored_by": "agent", "epistemic_state": "unverified", "body": "a cheap proxy"},
        {"id": "betweenness", "label": "Betweenness", "node_type": "metric", "provenance": "span-present",
         "authored_by": "agent", "epistemic_state": "unverified", "body": "path centrality"}],
        "edges": [{"source": "degree", "target": "betweenness", "relation": "bridges",
                   "provenance": "span-present", "authored_by": "agent", "epistemic_state": "unverified",
                   "span": "Degree bridges betweenness", "source_file": "second.md"}]},
        construction=name, source=str(second_src))


def test_construction_write_lands_in_alt_canon_only(engine, vault):
    """A `construction=` write is span-verified against its OWN source and lands under
    `.kg/constructions/<slug>/canon/`, never in the primary canon."""
    assert _primary_two_edges(engine)["dispositions"]["ACCEPTED"] == 2

    primary_canon = vault / "canon"
    before = {f.name: f.read_bytes() for f in primary_canon.glob("*.md")}

    out = _build_second_construction(engine, vault)
    # nodes degree + betweenness + the bridges edge all accepted, verified against second.md
    assert out["dispositions"]["ACCEPTED"] == 3, out
    assert out["dispositions"]["REJECTED"] == 0, out

    alt_canon = vault / ".kg" / "constructions" / "t2" / "canon"
    assert (alt_canon / "degree.md").exists(), "construction node missing from the alt canon"
    assert (alt_canon / "betweenness.md").exists()

    # regression: the primary canon (the construction=None default path) is byte-for-byte unchanged.
    after = {f.name: f.read_bytes() for f in primary_canon.glob("*.md")}
    assert after == before, "a construction write must not touch the primary canon"


def test_construction_span_verified_against_its_own_source(engine, vault):
    """The construction's spans are checked against the SECOND source — a span absent from it is a
    fabrication, exactly as on the primary path (the key-free build keeps the §1.5 guarantee)."""
    _second_source(vault)
    out = engine.kg_write({"edges": [
        {"source": "degree", "target": "betweenness", "relation": "bridges",
         "provenance": "span-present", "authored_by": "agent", "epistemic_state": "unverified",
         "span": "this sentence is nowhere in the second source", "source_file": "second.md"}]},
        construction="t2", source=str(vault / "second.md"))
    rejected = [d for d in out["details"] if d["disposition"] == "REJECTED"]
    assert rejected and "span-not-in" in rejected[0]["reason"], out


def test_generate_second_construction_yields_external_candidates(engine, vault):
    """kg_generate(second_construction=<name>) projects the alt canon in-session and cross-generates:
    the `degree ⇄ betweenness` bridge present in the second construction but absent in the primary is
    surfaced as `perturbation=external`, with NO `regroup` degrade note."""
    _primary_two_edges(engine)
    _build_second_construction(engine, vault)

    g = engine.kg_generate(mechanism="ensemble", second_construction="t2", k=10)
    assert "degraded to regroup" not in (g.get("note") or ""), g
    rationales = " ".join(c.get("rationale", "") for c in g["candidates"])
    assert "perturbation=external" in rationales, g
    # the external bridge joins the two metrics that were non-adjacent in the primary construction
    endpoints = {(c["source"], c["target"]) for c in g["candidates"]}
    assert frozenset(("degree", "betweenness")) in {frozenset(e) for e in endpoints}, g


def test_generate_missing_construction_degrades_to_regroup(engine, vault):
    """A construction name that was never built degrades to `regroup` with an honest note — it never
    crashes and never silently cross-generates against an empty graph."""
    _primary_two_edges(engine)
    g = engine.kg_generate(mechanism="ensemble", second_construction="never-built", k=10)
    assert "degraded to regroup" in (g.get("note") or ""), g
    # no external structure was invented from a non-existent construction
    assert "perturbation=external" not in " ".join(c.get("rationale", "") for c in g["candidates"]), g


def test_explicit_second_graph_path_still_wins(engine, vault):
    """`second_graph` (a pre-built graph.json path — the §11 escape hatch) takes precedence over
    `second_construction`, so the pre-built external-graph flow is unchanged."""
    _primary_two_edges(engine)
    _build_second_construction(engine, vault)
    # project t2 to get its graph.json path, then pass it EXPLICITLY as second_graph.
    path = engine._project_construction("t2")
    g = engine.kg_generate(mechanism="ensemble", second_graph=str(path),
                           second_construction="never-built", k=10)
    # used the explicit path (built ok) — not the bogus construction name — so no degrade note.
    assert "degraded to regroup" not in (g.get("note") or ""), g
    assert "perturbation=external" in " ".join(c.get("rationale", "") for c in g["candidates"]), g


def test_propose_routes_to_construction(engine, vault):
    """kg_propose(construction=…) routes the hypothesized lane to the alt canon exactly like kg_write —
    the candidate lands unverified in the construction, never in the primary."""
    second_src = _second_source(vault)
    out = engine.kg_propose({"edges": [
        {"source": "degree", "target": "betweenness", "relation": "bridges"}]},
        construction="t3", source=str(second_src))
    assert out["dispositions"]["ACCEPTED"] == 1, out
    alt_canon = vault / ".kg" / "constructions" / "t3" / "canon"
    assert (alt_canon / "degree.md").exists()
    assert not (vault / "canon" / "degree.md").exists(), "propose leaked into the primary canon"


def test_construction_slug_is_collision_safe():
    """Distinct names never share an on-disk construction dir (mirrors divergence _path_slug): a clean
    name round-trips; a lossy one gets a hash suffix so two names can't collapse to one canon."""
    from kg_engine.server import _construction_slug
    assert _construction_slug("evolutionary-computation") == "evolutionary-computation"  # clean: unchanged
    a = _construction_slug("proj A")
    b = _construction_slug("proj-A")
    assert a != b, "distinct names collapsed to one construction slug"
