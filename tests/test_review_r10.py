"""Regression pins for the exhaustive-review fix batch (review-r10, 2026-07-08).

One test per fixed finding, each written to FAIL on the pre-fix code and pass on the fix. IDs (H1/Mn/Ln)
match the review report. Windows-only branches (M3 canon `_win_pid_alive`, L10 canonmerge CRLF) are not
pinned here — they can't be exercised on the POSIX CI host — but their POSIX-observable twins are (L9).
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from kg_engine.canon import _pid_probe
from kg_engine.divergence.archive import continuous_bin
from kg_engine.divergence.config import Axis
from kg_engine.harness import specificity
from kg_engine.model import Disposition, EpistemicState, edge_id
from kg_engine.reconciler import Reconciler
from kg_engine.sources import split_sections


# ---- M2: an out-of-band demote of failed/rejected -> unverified erases §1.7 negative memory ----
def test_out_of_band_erasure_of_negative_memory_is_restored(engine):
    engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance", "authored_by": "agent"}]})
    eid = edge_id("degree", "approximates", "importance")
    engine.kg_ground(eid, "rejected", by="agent")  # a FAILURE state = permanent negative memory
    recon = Reconciler(engine.canon)
    recon.scan(full_sweep=True)  # baseline records `rejected`

    # hand-edit the canon: rejected -> unverified. No tool path produces `unverified`, and the merge
    # precedence makes failure states sticky, so this is an anomalous erasure the reconciler must undo.
    node = engine.canon.read_node("degree")
    next(e for e in node.edges if e.id == eid).epistemic_state = EpistemicState.UNVERIFIED
    engine.canon.write_one(node)

    report = recon.scan(full_sweep=True)
    assert eid in report.requarantined
    after = next(e for e in engine.canon.all_edges() if e.id == eid)
    assert after.epistemic_state == EpistemicState.REJECTED  # RESTORED, not left unverified


# ---- L18: reattach_after_reproject must not crash on a malformed (non-dict) graph.json ----
@pytest.mark.parametrize("blob", ["[1, 2, 3]", "null", '"hi"', '{"links": null}'])
def test_reattach_tolerates_malformed_graph_json(engine, vault, blob):
    recon = Reconciler(engine.canon)
    bad = vault / "bad_graph.json"
    bad.write_text(blob, encoding="utf-8")
    report = recon.reattach_after_reproject(bad)  # pre-fix: AttributeError/TypeError
    assert report is not None


# ---- M4: a `## ` line inside a fenced code block is NOT a section heading ----
def test_split_sections_ignores_headings_in_code_fence():
    text = "intro prose\n\n```\n## not a heading\nrm -rf x\n```\n\n## Real Section\nbody\n"
    titles = [t for t, _ in split_sections(text)]
    assert "not a heading" not in titles   # pre-fix: carved a spurious section here
    assert "Real Section" in titles         # a real heading after the fence still splits


# ---- M7: graph.json node/link order is a stable function of content, not write history ----
def test_graph_json_order_is_deterministic(engine):
    # two edges on ONE owner whose targets are in REVERSE-sorted file order, so insertion order
    # (zzz before bbb) differs from content order (bbb before zzz) — the emission sort must win.
    engine.kg_propose({"edges": [
        {"source": "aaa", "target": "zzz", "relation": "grounds"},
        {"source": "aaa", "target": "bbb", "relation": "grounds"}]})
    engine._ensure_projected()
    data = json.loads(engine.projector.graph_path.read_text(encoding="utf-8"))
    node_ids = [n["id"] for n in data["nodes"]]
    link_keys = [(l["source"], l["target"], l["id"]) for l in data["links"]]
    assert node_ids == sorted(node_ids)
    assert link_keys == sorted(link_keys)  # pre-fix: emitted in insertion order (aaa->zzz, aaa->bbb)


# ---- H1: a second construction is NEVER committed into the parent (user) repo ----
def test_construction_not_committed_to_parent_repo(engine, vault, source_path):
    engine.kg_write({"nodes": [{"label": "Alpha", "node_type": "compression"}]},
                    construction="exo", source=str(source_path))
    # the construction was built on disk...
    assert (vault / ".kg" / "constructions").exists()
    # ...but NOTHING under .kg/ was staged/committed into the user's repo (pre-fix: git walked up to the
    # parent repo and committed .kg/constructions/<slug>/canon/*.md into tracked history)
    tracked = subprocess.run(["git", "-C", str(vault), "ls-files"],
                             capture_output=True, text=True).stdout
    assert ".kg/constructions" not in tracked
    assert "constructions" not in tracked


# ---- M1: re-pointing a construction at a DIFFERENT source rebuilds from scratch (no stale merge) ----
def test_construction_rebuilt_on_source_change(engine, vault):
    src_a = vault / "second_a.md"; src_a.write_text("## S\nAlpha material.\n", encoding="utf-8")
    src_b = vault / "second_b.md"; src_b.write_text("## S\nGamma material.\n", encoding="utf-8")
    engine.kg_write({"nodes": [{"label": "Alpha", "node_type": "compression"}]},
                    construction="c", source=str(src_a))
    engine.kg_write({"nodes": [{"label": "Gamma", "node_type": "compression"}]},
                    construction="c", source=str(src_b))  # changed source -> wipe + rebuild
    labels = {n.label for n in engine._constructions["c"].canon.all_nodes()}
    assert "Gamma" in labels and "Alpha" not in labels  # pre-fix: both (stale merge)


# ---- L3: `source` without `construction` is refused, not silently dropped ----
def test_source_without_construction_is_refused(engine):
    with pytest.raises(ValueError):
        engine.kg_write({"nodes": [{"label": "X", "node_type": "compression"}]}, source="/some/where.md")


# ---- L6: a MISSING continuous value maps to the neutral mid-bin, not the extreme bin 0 ----
def test_continuous_bin_missing_is_mid_bin():
    ax = Axis(name="feasibility", type="continuous", range=(0.0, 1.0), bins=5)
    assert continuous_bin(ax, None) == 2          # mid, not 0 (pre-fix: 0, the far-fetched extreme)
    assert continuous_bin(ax, 0.05) == 0          # a real low value still bins low
    assert continuous_bin(ax, float("nan")) == 0  # garbage stays clamped, not neutralized


# ---- L8: query_graph floats bare hypothesized pins to the front of the unverified queue ----
def test_query_graph_floats_pins_to_front(engine):
    engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance", "authored_by": "agent"}]})  # degree>0, not hypothesized
    engine.kg_propose({"nodes": [{"label": "LonePin", "node_type": "compression"}]})  # degree 0, hypothesized
    engine._ensure_projected()
    res = engine.query_graph(epistemic_state="unverified", limit=1)
    assert res["nodes"] and res["nodes"][0]["provenance"] == "hypothesized"  # pre-fix: buried by degree DESC


# ---- L13: shortest_path never routes through a refuted (failed/rejected) edge (§1.7) ----
def test_shortest_path_excludes_refuted_edges(engine):
    engine.kg_propose({"edges": [
        {"source": "a", "target": "b", "relation": "grounds"},
        {"source": "b", "target": "c", "relation": "grounds"}]})
    engine.kg_ground(edge_id("a", "grounds", "b"), "failed", by="agent")  # refute the only a->b hop
    engine._ensure_projected()
    assert engine.shortest_path("a", "c") is None  # pre-fix: [a, b, c] through the refuted edge


# ---- L16: specificity() rejects a non-node-link dict with a clean ValueError, not a raw KeyError ----
def test_specificity_rejects_non_nodelink_dict():
    with pytest.raises(ValueError):
        specificity({"foo": 1}, [])  # pre-fix: KeyError: 'nodes' escaped _main's handler


# ---- L9: a lock record with a pid but NO host is assumed alive (never over-reclaimed) ----
@pytest.mark.skipif(os.name == "nt", reason="reaped-pid liveness is a POSIX guarantee")
def test_pid_probe_hostless_is_assumed_alive():
    p = subprocess.Popen(["true"])
    p.wait()  # reaped -> its pid no longer exists locally
    # hostless record: can't be probed against THIS host, so assume alive rather than reclaim a lease we
    # can't prove is dead (pre-fix: fell through to os.kill(dead_pid, 0) -> False)
    assert _pid_probe(p.pid, host="", my_host="some-other-host") is True
