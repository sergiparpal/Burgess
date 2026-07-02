"""Regression tests for review-r4 (the 2026-07 full-codebase review fixes).

Covers, in file order:
  1. BOM tolerance — a hand-edited note saved with a UTF-8 BOM parses instead of silently
     vanishing from every read (model.node_from_markdown strips a leading U+FEFF).
  2. The `owner` edge column — an incremental reproject DROPS a removed foreign-source edge
     (a hand-edited note carrying an edge whose `source:` names another node) instead of
     leaking a stale row; a pre-`owner` index.sqlite reads as outdated and heals via a full
     rebuild with the column populated.
  3. Egress re-scrub covers label/question/rationale (the §1.9 read-path gap), end-to-end
     through get_node and kg_agenda, while structural ids stay untouched.
  4. export._bridge_set tie-breaks by id ASCENDING among equal spec_betweenness — the same
     (value DESC, id ASC) order kg_context's bridge_metric SQL uses.
  5. advisory_geometry's grounded_mix counts INCOMING edges (G.edges() alone is out-only).
  6. generate.run_generators' FULL_TALLY_MAX_NODES gate leaves the surfaced slate unchanged.
  7. kg_write's canon-baseline cache — warm across sequential writes, invalidated by an
     out-of-band canon write (the cheap-signature key).
  8. build_engine_from_env's opt() treats an unsubstituted ${...} plugin option as unset.
  9. kg_scrub excludes identity (literal-placeholder) entries from redactions/categories.
 10. backend.run records a post-run projection failure instead of raising it out of the
     finally (which would mask the run's own outcome).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest

from kg_engine import generate
from kg_engine.advisory_geometry import _structural_descriptor
from kg_engine.canon import Canon
from kg_engine.export import _bridge_set
from kg_engine.model import Node, slug
from kg_engine.projector import Projector
from kg_engine.server import KGEngine, build_engine_from_env

# env vars that feed resolution in build_engine_from_env — cleared so the host env can't leak in
_RESOLUTION_ENV = ("KG_SOURCE_PATH", "CLAUDE_PLUGIN_OPTION_SOURCE_PATH", "KG_PROJECT_DIR",
                   "CLAUDE_PROJECT_DIR", "KG_PACK_PATH", "KG_DATA",
                   "CLAUDE_PLUGIN_OPTION_SENSITIVITY", "CLAUDE_PLUGIN_OPTION_METRICS_MODE")


# --- 1. BOM tolerance --------------------------------------------------------------------------

def test_bom_note_parses_and_survives_reads(canon: Canon):
    text = ("---\n"
            "id: bommed\n"
            "label: BOM Note\n"
            "edges:\n"
            "- source: bommed\n"
            "  target: other\n"
            "  relation: grounds\n"
            "  span: some span\n"
            "  epistemic_state: failed\n"
            "---\n"
            "body\n")
    # Windows Notepad's default "UTF-8" writes a BOM; read_text(encoding='utf-8') keeps it as U+FEFF
    (canon.notes_dir / "bommed.md").write_text("﻿" + text, encoding="utf-8")
    ids = {n.id for n in canon.all_nodes()}
    assert "bommed" in ids, "a BOM-prefixed note must not silently vanish from reads"
    node = canon.read_node("bommed")
    assert node.label == "BOM Note"
    # its §1.7 failure memory survives too (the worst casualty of the old silent drop)
    assert [e.epistemic_state.value for e in node.edges] == ["failed"]


# --- 2. the `owner` edge column ----------------------------------------------------------------

def _write_foreign_edge_vault(canon: Canon) -> None:
    (canon.notes_dir / "a.md").write_text(
        "---\nid: a\nlabel: A\nedges:\n"
        "- source: b\n  target: c\n  relation: grounds\n  span: some span\n---\n",
        encoding="utf-8")
    (canon.notes_dir / "b.md").write_text("---\nid: b\nlabel: B\n---\n", encoding="utf-8")


def test_incremental_reproject_drops_removed_foreign_source_edge(canon: Canon, tmp_path: Path):
    _write_foreign_edge_vault(canon)
    proj = Projector(canon, tmp_path / "derived")
    proj.project()
    con = sqlite3.connect(proj.db_path)
    try:
        rows = con.execute("SELECT id, owner FROM edges").fetchall()
    finally:
        con.close()
    assert rows == [("e_b__grounds__c", "a")]  # persisted in a.md, source b — owner is the FILE

    # hand-edit: remove the edge from a.md entirely
    (canon.notes_dir / "a.md").write_text("---\nid: a\nlabel: A\n---\n", encoding="utf-8")
    report = proj.project()
    assert not report.full_rebuild, "the leak lived on the incremental path — keep the test there"
    con = sqlite3.connect(proj.db_path)
    try:
        left = con.execute("SELECT id FROM edges").fetchall()
    finally:
        con.close()
    assert left == [], "derived layer retained an edge the canon no longer holds"


def test_pre_owner_edges_schema_reads_outdated_and_heals(canon: Canon, tmp_path: Path):
    (canon.notes_dir / "n.md").write_text(
        "---\nid: n\nlabel: N\nedges:\n"
        "- source: n\n  target: m\n  relation: grounds\n  span: s\n---\n",
        encoding="utf-8")
    proj = Projector(canon, tmp_path / "derived")
    proj.project()
    # regress the edges table to the pre-`owner` 11-column shape
    con = sqlite3.connect(proj.db_path)
    try:
        con.execute("DROP TABLE edges")
        con.execute("CREATE TABLE edges(id TEXT PRIMARY KEY, source TEXT, target TEXT, "
                    "relation TEXT, provenance TEXT, authored_by TEXT, epistemic_state TEXT, "
                    "span TEXT, source_file TEXT, confidence TEXT, confidence_score REAL)")
        con.commit()
    finally:
        con.close()
    assert proj._schema_outdated() is True
    report = proj.project()
    assert report.full_rebuild
    con = sqlite3.connect(proj.db_path)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(edges)")}
        rows = con.execute("SELECT id, owner FROM edges").fetchall()
    finally:
        con.close()
    assert "owner" in cols
    assert rows == [("e_n__grounds__m", "n")]


# --- 3. §1.9 egress re-scrub: label / question / rationale --------------------------------------

_SECRET = "sk-Ab12Cd34Ef56Gh78Ij90"  # mixed case: slug() lowercases ids, so ids never equal it


def test_scrub_egress_covers_label_question_rationale(engine: KGEngine):
    out = engine._scrub_egress({"label": f"x {_SECRET}", "question": f"q {_SECRET}",
                                "rationale": f"r {_SECRET}", "id": "some-id"})
    assert _SECRET not in out["label"]
    assert _SECRET not in out["question"]
    assert _SECRET not in out["rationale"]
    assert out["id"] == "some-id"  # structural fields stay untouched (referential integrity)


def test_get_node_and_agenda_scrub_canon_labels(engine: KGEngine):
    label = f"Leaky {_SECRET}"
    res = engine.kg_write({"nodes": [{"label": label, "node_type": "claim", "body": "b"}]})
    assert res["dispositions"]["ACCEPTED"] == 1
    nid = slug(label)
    # the canon stores the ORIGINAL (§1.9 protects the egress, not the vault)…
    assert _SECRET in engine.canon.read_node(nid).label
    # …but neither read surface returns it
    got = engine.get_node(nid)
    assert got and _SECRET not in (got.get("label") or "")
    agenda = engine.kg_agenda(limit=20)
    assert _SECRET not in json.dumps(agenda)


# --- 4. bridge-highlight tie-break parity ------------------------------------------------------

def test_bridge_set_tiebreak_is_id_ascending_like_kg_context():
    nodes = [{"id": f"n{i:02d}", "spec_betweenness": 1.0} for i in range(15)]
    picked = _bridge_set(nodes, gate_on=1)
    assert picked == {f"n{i:02d}" for i in range(10)}  # lowest ids among exact ties


# --- 5. grounded_mix counts incoming edges ------------------------------------------------------

def test_grounded_mix_counts_incoming_edges():
    G = nx.MultiDiGraph()
    G.add_edge("a", "x", key="e1", id="e1", relation="grounds", epistemic_state="grounded")
    G.add_edge("y", "z", key="e2", id="e2", relation="grounds", epistemic_state="unverified")
    cand = {"kind": "edge", "source": "x", "target": "y"}
    d = _structural_descriptor(cand, G, G.to_undirected(as_view=True), {})
    # x has ONLY an incoming grounded edge (out-only counting scored this 0.0), y one unverified out
    assert d["grounded_mix"] == 0.5


# --- 6. FULL_TALLY_MAX_NODES gate --------------------------------------------------------------

def test_full_tally_gate_preserves_surfaced_slate(monkeypatch):
    G = nx.MultiDiGraph()
    for nid, comm, sb in (("a", 0, 1), ("b", 0, 0), ("c", 1, 0), ("d", 1, 1)):
        G.add_node(nid, community=comm, structural_bridge=sb, degree=1,
                   specificity=1.0, gate_on=0)
    G.add_edge("a", "b", key="e1", id="e1", relation="grounds", epistemic_state="unverified")
    G.add_edge("b", "c", key="e2", id="e2", relation="grounds", epistemic_state="unverified")
    G.add_edge("c", "d", key="e3", id="e3", relation="grounds", epistemic_state="unverified")

    def surfaced(cands):
        # everything except `convergence`, which the approximate tally may legitimately undercount
        return [(c.mechanism, c.kind, c.source, c.target, c.relation, c.label,
                 round(c.score, 6)) for c in cands]

    exact = generate.run_generators(G, "all", k=5)
    monkeypatch.setattr(generate, "FULL_TALLY_MAX_NODES", 2)  # force the approximate-tally path
    gated = generate.run_generators(G, "all", k=5)
    assert surfaced(gated) == surfaced(exact)
    assert exact, "fixture must actually produce candidates for the comparison to mean anything"


# --- 7. kg_write canon-baseline cache ----------------------------------------------------------

def test_kg_write_baseline_cache_warm_and_invalidated(engine: KGEngine):
    payload = {"edges": [{"source": "degree", "target": "importance",
                          "relation": "approximates", "span": "Degree approximates importance"}]}
    r1 = engine.kg_write(payload)
    assert r1["dispositions"]["ACCEPTED"] == 1
    assert engine._baseline_cache is not None
    # the cached baseline saw write #1: an identical re-send dedups instead of double-writing
    r2 = engine.kg_write(payload)
    detail = next(d for d in r2["details"] if d["kind"] == "edge")
    assert "deduped" in detail["reason"]
    # an out-of-band canon write (write_one bypasses kg_write) moves the cheap signature: the
    # next baseline read re-parses and picks the new note up
    engine.canon.write_one(Node(id="oob-note", label="OOB"))
    assert "oob-note" in engine._canon_baseline()


# --- 8. ${...} plugin options read as unset ----------------------------------------------------

def test_plugin_option_placeholder_reads_as_unset(tmp_path: Path, monkeypatch):
    for key in _RESOLUTION_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_SENSITIVITY", "${user_config.sensitivity}")
    eng = build_engine_from_env(project=str(tmp_path))
    assert eng.sensitivity == "medium"  # the unsubstituted literal must not become the sensitivity


# --- 9. kg_scrub identity entries are bookkeeping, not redactions ------------------------------

def test_kg_scrub_identity_entries_not_counted(engine: KGEngine):
    out = engine.kg_scrub("the literal ⟦EMAIL:1⟧ appears in prose")
    assert out["redactions"] == 0 and out["categories"] == []
    out2 = engine.kg_scrub("mail real@example.com about it")
    assert out2["redactions"] == 1 and out2["categories"] == ["EMAIL"]


# --- 10. backend post-run projection failure is recorded, never raised -------------------------

def test_backend_projection_failure_recorded_not_raised(engine: KGEngine, monkeypatch):
    from kg_engine.backend import BackendExtractor

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=json.dumps({"nodes": [], "edges": []}))])))
    ext = BackendExtractor(engine, client=fake_client)

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine.projector, "project", _boom)
    out = ext.run()  # must NOT raise out of the finally
    assert "boom" in out.get("projection_error", "")
    assert out["failed_sections"] == []  # the extraction outcome is intact, not masked
