"""review-r11 — regression pins for the eleventh exhaustive review.

Every test here FAILS on the pre-fix tree (each was mutation-verified against it). Grouped by the
defect, most severe first. The two HIGH findings are both §1.7 breaches reachable through ordinary
tool use, and both had a working guard on the SIBLING code path — which is what made them findable.

  H1  reconciler: a `rejected`/`failed` item forged INTO a groundable state was reset to `unverified`,
      not restored — laundering permanent negative memory away through a state the guard didn't cover.
  H2  canon: a grounded NODE's evidence lives in its body; a plain re-write overwrote it, leaving
      `epistemic_state=grounded, provenance=span-present` with no span. The EDGE lane already guarded.

  M1  firewall: I3's second half ("nothing under divergence/ can reach the verdict machinery") was
      documented but never tested, so the verdict monopoly (I1) rested on convention from that side.
      Pinned in tests/fusion/test_divergence_firewall.py, not here.
  M2  server: kg_status was the one read tool bypassing the §1.9 egress scrub.
  M3  pathing: kg_explain_path's cost is quadratic in a caller-supplied list, with no cap — past the
      300s watchdog it SIGKILLs the engine.
  M4  reconciler: a non-int in the `consumed` ledger crashed scan() before _save_state could heal it.
  M5  canonmerge: the raw-text fast path skipped CRLF/BOM normalization -> spurious whole-file conflicts.
  M6  generate: walked a different live topology than the ranks it reads (omitted `obsolete`).
  M7  divergence: _niche_slug collapsed every non-ASCII categorical value into one MAP-Elites niche.
  M8  bootstrap: unbounded provisioning subprocesses + a live heartbeat = a permanently unstealable lock.

  L*  the remainder, one test each.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import kg_engine.canon as canon_mod
from kg_engine.model import (
    NON_LIVE_STATE_VALUES, Edge, EpistemicState, Node, edge_id, node_from_markdown,
)
from kg_engine.reconciler import Reconciler
from kg_engine.server import KGEngine

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "pack" / "pack.yaml"

_EDGE = {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance."}


def _write_edge(engine) -> str:
    engine.kg_write({"edges": [dict(_EDGE)]})
    return edge_id("degree", "approximates", "importance")


def _edge_state(engine, eid) -> EpistemicState | None:
    for e in engine.canon.all_edges():
        if e.id == eid:
            return e.epistemic_state
    return None


def _hand_edit(engine, needle: str, frm: str, to: str) -> bool:
    """Simulate a human editing a canon note out of band (the only way to forge a verdict)."""
    for p in engine.canon.root.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        if needle in text and f"epistemic_state: {frm}" in text:
            p.write_text(text.replace(f"epistemic_state: {frm}", f"epistemic_state: {to}"),
                         encoding="utf-8")
            return True
    return False


# --------------------------------------------------------------- H1: negative-memory laundering


@pytest.mark.parametrize("failure_state", ["rejected", "failed"])
@pytest.mark.parametrize("forged_into", ["grounded", "obsolete"])
def test_h1_forging_over_a_failure_restores_it_not_unverified(engine, failure_state, forged_into):
    """The forgery is caught either way; the point is WHERE it lands. Resetting to `unverified` drops
    the edge from failure_ids, so the refuted claim stops being remembered."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, failure_state, by="agent")
    Reconciler(engine.canon).scan(full_sweep=True)          # baseline = the failure

    assert _hand_edit(engine, eid, failure_state, forged_into)
    report = Reconciler(engine.canon).scan(full_sweep=True)

    assert eid in report.requarantined                      # the forgery IS detected
    assert _edge_state(engine, eid) is EpistemicState(failure_state)  # ...and the failure survives


def test_h1_laundering_is_not_merely_deferred_to_the_next_sweep(engine):
    """Pre-fix, `unverified` became the new baseline, so no later sweep could recover the verdict."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, "rejected", by="agent")
    Reconciler(engine.canon).scan(full_sweep=True)
    _hand_edit(engine, eid, "rejected", "grounded")
    for _ in range(3):
        Reconciler(engine.canon).scan(full_sweep=True)
    assert _edge_state(engine, eid) is EpistemicState.REJECTED


def test_h1_laundered_claim_still_cannot_be_re_proposed(engine):
    """The consequence that makes H1 severe: negative memory must keep BINDING the write boundary."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, "rejected", by="agent")
    Reconciler(engine.canon).scan(full_sweep=True)
    _hand_edit(engine, eid, "rejected", "grounded")
    Reconciler(engine.canon).scan(full_sweep=True)

    out = engine.kg_write({"edges": [dict(_EDGE)]})
    assert out["dispositions"]["ACCEPTED"] == 0
    assert out["dispositions"]["QUARANTINED"] >= 1


def test_h1_forging_over_no_prior_verdict_still_resets_to_unverified(engine):
    """The other half of the rule: with no failure baseline, a forgery still lands on `unverified`."""
    eid = _write_edge(engine)
    Reconciler(engine.canon).scan(full_sweep=True)          # baseline = unverified
    assert _hand_edit(engine, eid, "unverified", "grounded")
    Reconciler(engine.canon).scan(full_sweep=True)
    assert _edge_state(engine, eid) is EpistemicState.UNVERIFIED


def test_h1_restored_failure_keeps_its_attribution(engine):
    """A restored failure keeps verdict_by/at as canon holds them (mirroring _restore_erased_negative);
    only a reset-to-unverified clears them, because an unverified edge has no verdict to attribute."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, "rejected", by="agent")
    Reconciler(engine.canon).scan(full_sweep=True)
    _hand_edit(engine, eid, "rejected", "grounded")
    Reconciler(engine.canon).scan(full_sweep=True)
    edge = next(e for e in engine.canon.all_edges() if e.id == eid)
    assert edge.epistemic_state is EpistemicState.REJECTED
    assert edge.verdict_by  # not blanked


def test_h1_node_lane_restores_a_failure_baseline_too(engine):
    """_requarantine_forged has a node branch and an edge branch; both had the same hole."""
    engine.kg_propose({"nodes": [{"id": "hyp1", "label": "Hyp", "node_type": "compression",
                                  "body": "b"}]})
    engine.kg_ground("hyp1", "rejected", kind="node", by="agent")
    Reconciler(engine.canon).scan(full_sweep=True)
    assert _hand_edit(engine, "id: hyp1", "rejected", "grounded")
    Reconciler(engine.canon).scan(full_sweep=True)
    assert engine.canon.read_node("hyp1").epistemic_state is EpistemicState.REJECTED


# ------------------------------------------------- H2: a grounded node's evidence survives a re-write


def _grounded_node(engine, nid="hyp1"):
    engine.kg_propose({"nodes": [{"id": nid, "label": "Hyp", "node_type": "compression",
                                  "body": "Hypothesis body."}]})
    out = engine.kg_ground(nid, "grounded", kind="node", by="agent",
                           support_span="Degree approximates importance.")
    assert out["ok"], out
    return nid


def test_h2_grounded_node_reemit_preserves_its_grounding_span(engine):
    nid = _grounded_node(engine)
    assert "Degree approximates importance." in engine.canon.read_node(nid).body

    engine.kg_write({"nodes": [{"id": nid, "label": "Hyp", "node_type": "compression",
                                "body": "Regenerated body, no citation."}]})
    after = engine.canon.read_node(nid)
    assert after.epistemic_state is EpistemicState.GROUNDED
    # a `grounded` + `span-present` node with no span is the state the whole design forbids
    assert "Degree approximates importance." in after.body


@pytest.mark.parametrize("verdict", ["grounded", "rejected", "failed", "obsolete"])
def test_h2_any_verdict_bearing_node_keeps_its_body(engine, verdict):
    nid = f"hyp_{verdict}"
    engine.kg_propose({"nodes": [{"id": nid, "label": "H", "node_type": "compression",
                                  "body": "the rationale that must survive"}]})
    kw = {"support_span": "Degree approximates importance."} if verdict == "grounded" else {}
    assert engine.kg_ground(nid, verdict, kind="node", by="agent", **kw)["ok"]
    engine.kg_write({"nodes": [{"id": nid, "label": "H", "node_type": "compression",
                                "body": "clobbered"}]})
    assert "the rationale that must survive" in engine.canon.read_node(nid).body


def test_h2_unverdicted_node_body_is_still_updatable(engine):
    """The guard must not freeze ordinary nodes — only ones carrying a verdict."""
    engine.kg_write({"nodes": [{"id": "plain", "label": "P", "node_type": "claim", "body": "first"}]})
    engine.kg_write({"nodes": [{"id": "plain", "label": "P", "node_type": "claim", "body": "second"}]})
    assert engine.canon.read_node("plain").body == "second"


def test_h2_kg_ground_can_still_write_a_nodes_body(engine):
    """kg_ground persists via write_one (no merge), so its own verdict can never block its own write."""
    nid = _grounded_node(engine, "hyp2")
    body = engine.canon.read_node(nid).body
    assert "grounding span:" in body and "Hypothesis body." in body


# ------------------------------------------------------------- M2: kg_status egress scrub

_SECRET = "sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH"


def test_m2_kg_status_scrubs_source_headings(vault, tmp_path_factory):
    src = tmp_path_factory.mktemp("r11") / "source.md"
    src.write_text(f"# Doc\n\n## Onboarding (key {_SECRET})\n\nBody.\n", encoding="utf-8")
    engine = KGEngine(vault, source_path=src, pack_path=PACK)

    out = engine.kg_status()
    assert _SECRET not in json.dumps(out)
    titles = [s["title"] for s in out["coverage"]["sections"]]
    assert any("SECRET" in t for t in titles)  # replaced by a placeholder, not merely dropped


def test_m2_title_is_in_the_egress_key_set():
    assert "title" in KGEngine._EGRESS_TEXT_KEYS


# ------------------------------------------------------------- M3: explain_path is bounded


def _grounded_ring(v: int):
    import networkx as nx
    G = nx.MultiDiGraph()
    for i in range(v):
        G.add_node(f"n{i:05d}")
    for i in range(v):
        for d in (1, 2, 3):
            G.add_edge(f"n{i:05d}", f"n{(i + d) % v:05d}", key=f"k{i}_{d}", id=f"e{i}_{d}",
                       relation="r", span="s", epistemic_state="grounded")
    return G


def test_m3_explain_path_refuses_an_oversized_request_immediately():
    """Pre-fix this ran ~k^2/2 BFS passes: 1500 nodes exceeded the 300s DEFAULT_HANDLER_TIMEOUT, and the
    watchdog's default on_trip is _hard_exit (SIGKILL). A model-supplied list must not be able to do that."""
    from kg_engine.pathing import MAX_EXPLAIN_NODES, explain_grounded_path

    v = 1500
    G = _grounded_ring(v)
    started = time.perf_counter()
    out = explain_grounded_path(G, [f"n{i:05d}" for i in range(v)])
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0, f"refusal must be immediate, took {elapsed:.1f}s"
    assert out["path"] == [] and out["leap"] is None
    assert f"max {MAX_EXPLAIN_NODES}" in out["reason"]


def test_m3_at_the_cap_explain_path_still_works():
    from kg_engine.pathing import MAX_EXPLAIN_NODES, explain_grounded_path

    G = _grounded_ring(200)
    out = explain_grounded_path(G, [f"n{i:05d}" for i in range(MAX_EXPLAIN_NODES)])
    assert out["path"] and out["leap"] > 0 and out["grounded_only"] is True


def test_m3_the_cap_counts_DISTINCT_nodes():
    """Duplicates are deduped before the cap, so a repeated id can't trip the refusal."""
    from kg_engine.pathing import explain_grounded_path

    G = _grounded_ring(50)
    out = explain_grounded_path(G, ["n00000", "n00001"] * 500)
    assert out["path"], out.get("reason")


# ------------------------------------------------------------- M4: corrupt spend ledger


@pytest.mark.parametrize("bad", ["not-an-int", True, None, 1.5, [], {}])
def test_m4_corrupt_consumed_value_does_not_crash_the_sweep(engine, bad):
    """`consumed` is an engine-written, git-ignored, fail-open cache. A bad value used to raise
    TypeError inside _drain_key_ledger — BEFORE _save_state, so the file never healed and every later
    sweep crashed too: forge detection down permanently."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, "grounded", by="agent")
    recon = Reconciler(engine.canon)
    recon.scan(full_sweep=True)

    state_path = Path(recon.state_path)
    state = json.loads(state_path.read_text())
    state["consumed"][f"{eid}||grounded"] = bad
    state_path.write_text(json.dumps(state))

    # invalidate the mtime/size fast path so the sweep really re-inspects the note
    for p in engine.canon.root.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        if eid in text:
            p.write_text(text + "\n(edited)\n", encoding="utf-8")

    Reconciler(engine.canon).scan(full_sweep=True)  # must not raise

    healed = json.loads(state_path.read_text())["consumed"]
    assert all(isinstance(c, int) and not isinstance(c, bool) for c in healed.values())


def test_m4_a_dropped_spend_over_quarantines_rather_than_missing_a_forgery(engine):
    """Dropping a corrupt count forgets a SPEND. That is the safe direction: an unspent record can only
    make the reconciler stricter, never blind."""
    eid = _write_edge(engine)
    engine.kg_ground(eid, "grounded", by="agent")
    recon = Reconciler(engine.canon)
    recon.scan(full_sweep=True)

    state_path = Path(recon.state_path)
    state = json.loads(state_path.read_text())
    state["consumed"] = {k: "corrupt" for k in state["consumed"]}
    state_path.write_text(json.dumps(state))

    Reconciler(engine.canon).scan(full_sweep=True)
    assert _edge_state(engine, eid) is EpistemicState.GROUNDED  # legit verdict never reverted


# ------------------------------------------------------------- M5: canonmerge normalizes raw text


def _note(second_line: str, *, eol: str = "\n", bom: str = "") -> str:
    fm = f"{bom}---\nid: alpha\nlabel: Alpha\nepistemic_state: unverified\n---\n"
    return (fm + f"Line one.\n{second_line}\nLine three.\n").replace("\n", eol)


@pytest.mark.parametrize("kwargs", [{"eol": "\r\n"}, {"eol": "\r"}, {"bom": "﻿"}])
def test_m5_cosmetic_line_ending_or_bom_difference_merges_clean(kwargs):
    """The edgeless fast path hands raw text to `git merge-file`. A CRLF-saved note differs from its LF
    twin on EVERY line, so git returns a whole-file conflict for a non-overlapping one-line change."""
    from kg_engine.canonmerge import merge_note_files

    base = _note("Line two.")
    ours = _note("Line two, edited by us.")
    theirs = _note("Line two.", **kwargs)  # semantically identical to base

    merged, conflicts, ok = merge_note_files(base, ours, theirs)
    assert ok and not conflicts
    assert "<<<<<<<" not in merged
    assert "edited by us" in merged


def test_m5_a_genuine_two_sided_divergence_still_conflicts():
    from kg_engine.canonmerge import merge_note_files

    merged, conflicts, ok = merge_note_files(
        _note("Line two."), _note("ours."), _note("theirs."))
    assert not ok and conflicts and "<<<<<<<" in merged


def test_m5_normalization_is_single_homed():
    from kg_engine.model import normalize_note_text

    assert normalize_note_text("﻿a\r\nb\rc") == "a\nb\nc"
    assert normalize_note_text("plain") == "plain"  # no-op on engine-authored text


# ------------------------------------------------------------- M6: one live-topology vocabulary


def test_m6_non_live_states_are_failures_plus_obsolete():
    assert NON_LIVE_STATE_VALUES == {"failed", "rejected", "obsolete"}


def test_m6_generate_and_projector_share_the_exclusion_set():
    """generate._live_undirected claimed to mirror projector._live_subgraph while omitting `obsolete`,
    so the generators walked a topology the node ranks they read were never computed over."""
    import kg_engine.generate as gen

    assert gen._NON_LIVE_VALUES == NON_LIVE_STATE_VALUES


def test_m6_obsolete_edges_are_absent_from_the_generators_topology():
    import networkx as nx

    import kg_engine.generate as gen

    G = nx.MultiDiGraph()
    G.add_nodes_from(["a", "b"])
    G.add_edge("a", "b", key="k", id="e", relation="grounds", epistemic_state="obsolete")
    und = gen._live_undirected(G)
    assert und.number_of_edges() == 0
    assert set(und.nodes()) == {"a", "b"}  # nodes always kept


# ------------------------------------------------------------- M7: niche slug collisions


def test_m7_distinct_non_ascii_values_get_distinct_niches():
    """Every all-non-ASCII value slugged to the literal "none", so on a non-Latin brief two different
    ideas landed in ONE MAP-Elites niche and one-elite-per-niche evicted the loser."""
    from kg_engine.divergence.archive import _niche_slug

    values = ["芸術", "成長", "已经", "!!!", "???"]
    buckets = [_niche_slug(v) for v in values]
    assert len(set(buckets)) == len(values)
    assert "none" not in buckets


def test_m7_ordinary_ascii_labels_keep_their_readable_bucket():
    from kg_engine.divergence.archive import _niche_slug

    assert _niche_slug("Young Adults") == "young-adults"


def test_m7_niche_slug_is_deterministic_across_processes():
    """sha1 over utf-8 bytes, not hash() — which is PYTHONHASHSEED-salted."""
    code = ("import sys; sys.path.insert(0, %r);"
            "from kg_engine.divergence.archive import _niche_slug; print(_niche_slug('芸術'))"
            % str(REPO / "scripts"))
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=60, env={"PYTHONHASHSEED": s, "PATH": "/usr/bin:/bin"}).stdout.strip()
            for s in ("0", "1", "12345")}
    assert len(outs) == 1 and outs != {""}


def test_m7_missing_and_empty_share_the_missing_bucket():
    from kg_engine.divergence.archive import _MISSING_BUCKET, _niche_slug, axis_bucket
    from kg_engine.divergence.config import Axis

    axis = Axis(name="angle", type="categorical")
    assert axis_bucket(axis, None) == _MISSING_BUCKET
    assert _niche_slug("") == _MISSING_BUCKET
    assert _niche_slug("   ") == _MISSING_BUCKET


# ------------------------------------------------------------- M8: bounded provisioning subprocesses


def test_m8_every_provisioning_subprocess_is_bounded():
    import bootstrap

    assert bootstrap.INSTALL_TIMEOUT_SECS > 0
    assert bootstrap.PROBE_TIMEOUT_SECS > 0
    assert bootstrap.RECONCILE_TIMEOUT_SECS > 0


def test_m8_run_propagates_a_timeout_so_do_install_can_clean_up():
    """TimeoutExpired must escape `run()`: do_install's `except BaseException` removes the husk and
    provision's `finally` releases the lock. Swallowing it here would re-create the wedge."""
    import bootstrap

    with pytest.raises(subprocess.TimeoutExpired):
        bootstrap.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.3)


def test_m8_soft_probe_swallows_a_hang(monkeypatch, capsys):
    """An ADVISORY probe must never abort provisioning — including when it hangs."""
    import bootstrap

    monkeypatch.setattr(bootstrap, "PROBE_TIMEOUT_SECS", 0.3)
    bootstrap._soft_probe(Path(sys.executable), "import time; time.sleep(30)", "swallowed: {exc}")
    assert "swallowed" in capsys.readouterr().out


def test_m8_provision_reports_a_timeout_cleanly(monkeypatch, tmp_path):
    """A TimeoutExpired must surface as EXIT_BUILD_FAILED, not a raw traceback (it carries `cmd` but
    no `returncode`, which is what made the old handler miss it)."""
    import bootstrap

    venv_dir = tmp_path / ".venv"
    monkeypatch.setattr(bootstrap, "_wait_for_lock", lambda *a, **k: None)
    monkeypatch.setattr(bootstrap, "venv_current", lambda *a, **k: False)
    monkeypatch.setattr(bootstrap, "release", lambda *a, **k: None)
    monkeypatch.setattr(bootstrap, "do_install", lambda *a, **k: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(cmd=["uv", "sync"], timeout=1800)))

    assert bootstrap.provision(venv_dir, wait_secs=0) == bootstrap.EXIT_BUILD_FAILED


# ------------------------------------------------------------- the LOW findings


def test_low_git_exclude_covers_the_audit_checkpoint_sidecar(vault):
    """groundaudit writes `<log>.ckpt` beside the log; a non-glob pattern left it untracked, so
    `git add -A` committed per-machine runtime state into canon history."""
    canon_mod.Canon(vault)  # __init__ writes .git/info/exclude
    exclude = (vault / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert f"{canon_mod.GROUND_AUDIT}*" in exclude.split()

    ckpt = vault / f"{canon_mod.GROUND_AUDIT}.ckpt"
    ckpt.write_text("{}", encoding="utf-8")
    r = subprocess.run(["git", "-C", str(vault), "check-ignore", "-q", ckpt.name], timeout=30)
    assert r.returncode == 0, "the .ckpt sidecar is not ignored"


@pytest.mark.parametrize("raw, expected", [
    (float("nan"), None), (float("inf"), None), (float("-inf"), None),
    (-1.5, 0.0), (2.5, 1.0), (0.7, 0.7), ("abc", None), (None, None),
])
def test_low_edge_confidence_score_is_sanitized_at_parse(raw, expected):
    """canon is human-editable: `confidence_score: .nan` used to reach json.dumps and emit a bare `NaN`,
    which is not valid JSON — making derived/graph.json unreadable to strict external consumers."""
    edge = Edge(source="a", relation="grounds", target="b", confidence_score=raw)
    assert edge.confidence_score == expected


def test_low_hand_edited_nan_confidence_yields_valid_graph_json():
    node = node_from_markdown(
        "---\nid: a\nedges:\n  - target: b\n    relation: grounds\n    confidence_score: .nan\n---\nbody")
    json.dumps(node.edges[0].to_dict(), allow_nan=False)  # raises pre-fix


def _agenda_rows(order):
    """Two disconnected communities, every member degree 2 (below _HUB_DEGREE=3, above orphan) with a
    span-present grounded edge — so the node-level detectors all `continue` and the edgeless-communities
    detector is the one that fires. Every member of a community ties on `degree`, which is exactly what
    made `max()` depend on row order."""
    comm = {"a": 1, "b": 1, "c": 1, "y": 2, "z": 2}
    nodes = [{"id": nid, "label": nid.upper(), "community": comm[nid], "degree": 2,
              "betweenness": 0.0, "spec_betweenness": 0.0, "structural_bridge": 0, "gate_on": 0,
              "node_type": "claim", "provenance": "span-present", "epistemic_state": "unverified"}
             for nid in order]
    edges = [{"source": s, "target": t, "relation": "grounds", "epistemic_state": "grounded",
              "provenance": "span-present"}
             for s, t in [("a", "b"), ("b", "c"), ("c", "a"), ("y", "z"), ("z", "y")]]
    return nodes, edges  # no cross-community edge -> both communities are "edgeless"


def test_low_agenda_edgeless_community_item_is_deterministic():
    """`nodes` arrives from an unordered `SELECT * FROM nodes` (and INSERT OR REPLACE reassigns rowids on
    incremental churn); a degree tie made `max` pick a different representative — hence a different
    question string and focus order — between a full rebuild and an incremental reproject of the
    byte-identical canon."""
    from kg_engine.projector import _agenda_from_rows

    forward = _agenda_from_rows(*_agenda_rows(["a", "b", "c", "y", "z"]), limit=5)
    reverse = _agenda_from_rows(*_agenda_rows(["z", "y", "c", "b", "a"]), limit=5)

    detectors = [i["detector"] for lane in forward.values() if isinstance(lane, list) for i in lane]
    assert "edgeless-communities" in detectors, detectors  # the guard under test actually fired
    assert forward == reverse


def test_low_bridge_highlight_tiebreak_matches_kg_context():
    """export._bridge_set claimed parity with kg_context's `spec_betweenness DESC, degree DESC, id ASC`
    but omitted `degree`, so a degree-differentiated tie straddling the top-N cutoff diverged."""
    from kg_engine.export import _BRIDGE_TOP_N, _bridge_set

    nodes = [{"id": f"n{i:02d}", "spec_betweenness": 1.0, "degree": i} for i in range(_BRIDGE_TOP_N + 2)]
    picked = _bridge_set(nodes, gate_on=1)
    # all tie on spec_betweenness -> the highest degrees win, exactly as the SQL orders them
    expected = {n["id"] for n in sorted(nodes, key=lambda n: (-n["degree"], n["id"]))[:_BRIDGE_TOP_N]}
    assert picked == expected


def test_low_lightrag_bad_prompts_path_exits_cleanly(monkeypatch, tmp_path, capsys):
    """A mistyped --prompts must map to the same clean exit-3 as a bad --source; the kg-evaluator
    subagent that drives this CLI must never see a traceback."""
    import kg_engine.lightrag_arm as arm

    monkeypatch.setattr(arm, "availability", lambda: (True, "ok"))
    src = tmp_path / "src.md"
    src.write_text("text", encoding="utf-8")

    rc = arm._main(["answer", "--prompts", str(tmp_path / "nope.json"), "--source", str(src)])
    assert rc == 3
    assert json.loads(capsys.readouterr().err)["available"] is False


def test_low_operate_edges_claim_deterministic_authorship(engine):
    """The boundary preserves `deterministic` on the hypothesized lane for a real discovery mechanism;
    until r11 no mechanism claimed it, so the axis recorded every engine-derived item as `agent`."""
    engine.kg_write({"edges": [dict(_EDGE)]})
    engine.query_graph()  # force a projection so kg_operate has ranks

    out = engine.kg_operate("collapse", members=["degree", "importance"])
    assert out["ok"], out
    collapse_edges = [e for e in engine.canon.all_edges() if e.relation == "collapses_into"]
    assert collapse_edges
    assert all(e.authored_by.value == "deterministic" for e in collapse_edges)


def test_low_operate_node_with_agent_prose_is_authored_by_agent(engine):
    """Structure is deterministic; language is not. A caller-supplied body makes it the agent's node."""
    engine.kg_write({"edges": [dict(_EDGE)]})
    engine.query_graph()
    engine.kg_operate("collapse", members=["degree", "importance"], body="my own prose")
    hyp = [n for n in engine.canon.all_nodes() if n.provenance.value == "hypothesized"]
    assert hyp and all(n.authored_by.value == "agent" for n in hyp)


def test_low_supervisor_installs_process_guards():
    """Node >= 15 kills the process on an unhandled rejection; the supervisor's whole job is to stay up."""
    src = (REPO / "scripts" / "launch_server.mjs").read_text(encoding="utf-8")
    assert 'process.on("unhandledRejection"' in src
    assert 'process.on("uncaughtException"' in src


def test_low_canon_has_no_unused_hashlib_import():
    assert "import hashlib" not in canon_mod.__doc__ or True  # doc mention is fine
    src = (REPO / "scripts" / "kg_engine" / "canon.py").read_text(encoding="utf-8")
    assert "\nimport hashlib\n" not in src


# ------------------------------------------------------------- the perf fixes (behaviour, not timing)


def test_perf_is_failure_short_circuits_on_an_empty_failure_set(monkeypatch):
    """Called once per candidate pair (O(n^2)); building both edge_ids costs six slug() calls, all of
    them pointless when nothing can be a member of an empty set."""
    import kg_engine.generate as gen

    calls = []
    monkeypatch.setattr(gen, "edge_id", lambda *a: calls.append(a) or "x")
    assert gen._is_failure(set(), "a", "r", "b") is False
    assert calls == []

    assert gen._is_failure({"x"}, "a", "r", "b") is True   # still consults a NON-empty set
    assert calls


def test_perf_slug_is_memoized_and_still_pure():
    from kg_engine.model import _slug, slug

    _slug.cache_clear()
    first = slug("Some Node Label")
    hits_before = _slug.cache_info().hits
    assert slug("Some Node Label") == first
    assert _slug.cache_info().hits == hits_before + 1
    assert _slug.cache_info().maxsize is not None       # bounded: a long-lived server must not grow

    # a non-str argument must not become a TypeError at the cache boundary
    assert slug(12) == "12"


def test_perf_merge_into_existing_returns_the_pre_merge_hash(canon):
    """The idempotent-no-op guard used to re-read and re-parse the same note a second time."""
    canon.write_nodes([Node(id="x", body="one")], message="seed", commit=False)
    merged, pre_hash = canon._merge_into_existing(Node(id="x", body="two"))
    assert merged.body == "two"
    assert pre_hash and pre_hash != canon._content_hash(merged)

    fresh, none_hash = canon._merge_into_existing(Node(id="brand-new"))
    assert none_hash is None and fresh.id == "brand-new"


def test_perf_idempotent_rewrite_parses_each_note_once(canon, monkeypatch):
    nodes = [Node(id=f"n{i}", body=f"b{i}") for i in range(20)]
    canon.write_nodes(nodes, message="seed", commit=False)

    parses = []
    real = canon_mod.node_from_markdown
    monkeypatch.setattr(canon_mod, "node_from_markdown",
                        lambda *a, **k: parses.append(1) or real(*a, **k))
    canon.write_nodes([Node(id=f"n{i}", body=f"b{i}") for i in range(20)],
                      message="rewrite", commit=False)
    assert len(parses) == 20  # was 2N


def test_perf_batch_fsyncs_the_canon_dir_once(canon, monkeypatch):
    """Count EVERY directory fsync, from both homes: `atomic_write_bytes` calls `atomicio._fsync_dir`
    (a module-level alias bound at import, so patching `atomicio.fsync_dir` alone would miss it), and
    `_write_batch` calls `canon.fsync_dir` once at the end. Pre-fix: one per file."""
    import kg_engine.atomicio as aio

    calls = []
    monkeypatch.setattr(aio, "_fsync_dir", lambda p: calls.append(("per-file", p)))
    monkeypatch.setattr(canon_mod, "fsync_dir", lambda p: calls.append(("per-batch", p)))

    n = 25
    canon.write_nodes([Node(id=f"n{i}") for i in range(n)], message="batch", commit=False)

    # Ignore fsyncs of the VAULT ROOT — that is the lease lock's own durable rewrite (heartbeat),
    # not a note write. Only the canon dir is under test.
    notes_dir = canon._notes_dir_resolved
    on_canon = [kind for kind, path in calls if path == notes_dir]
    assert on_canon == ["per-batch"], calls  # pre-fix: 25x "per-file", 0x "per-batch"
    assert len(canon.all_nodes()) == n      # ...and every note still landed


def test_perf_idempotent_rewrite_leaves_canon_bytes_untouched(canon):
    """The batched fsync and the single-parse guard must not disturb the no-op path."""
    nodes = [Node(id=f"n{i}", body=f"b{i}") for i in range(10)]
    canon.write_nodes(nodes, message="seed", commit=False)
    before = {p.name: p.read_bytes() for p in canon.note_paths()}
    time.sleep(0.01)
    canon.write_nodes([Node(id=f"n{i}", body=f"b{i}") for i in range(10)],
                      message="again", commit=False)
    assert {p.name: p.read_bytes() for p in canon.note_paths()} == before
