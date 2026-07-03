"""I10 — archive ephemerality (FUSION_PLAN Stage 2).

No MAP-Elites archive file persists across sessions. Only pins, discards,
comparisons and project/session metadata persist (project-local). After a full
divergence round in a temp project, every geometry artifact sits inside the
session scope (the state home's ``session/`` zone) and a new session wipes it.
"""
from __future__ import annotations

import os
from pathlib import Path

from kg_engine.divergence import pipeline
from kg_engine.divergence.state import State

AXES = {
    "domain": "d",
    "unit_of_generation": "idea",
    "axes": [
        {"name": "form", "type": "categorical"},
        {"name": "mechanism", "type": "open", "primary_novelty": True},
    ],
    "slate_size": 4,
    "candidates_per_generation": 6,
}

GEOMETRY_FILES = {"archive.json", "candidates.json", "embeddings.npz",
                  "mech_embeddings.npz", "open_nicher.json",
                  # legacy pre-npz vector store names (review-r6): the detector keeps catching
                  # an older engine's artifacts so a mixed-version state dir can't dodge I10.
                  "embeddings.json", "mech_embeddings.json"}


def _cands(n, tag=""):
    return [
        {"id": f"c{tag}{i}", "text": f"distinct idea {tag}{i} about topic {i}",
         "descriptor": {"form": f"v{i}", "mechanism": f"approach {tag}{i}"}}
        for i in range(n)
    ]


def _full_round(home: Path, session: str, tag: str = "") -> dict:
    pipeline.init_project("proj", AXES, seed=3, home=home, session=session)
    out = pipeline.ingest("proj", _cands(6, tag), AXES, seed=3, home=home)
    pipeline.remember("proj", {"type": "pin", "id": f"c{tag}0"}, home=home)
    pipeline.remember("proj", {"type": "discard", "id": f"c{tag}1"}, home=home)
    pipeline.parents("proj", k=2, seed=3, home=home)
    pipeline.metrics("proj", home=home)
    return out


def test_i10_geometry_confined_to_session_scope(tmp_path, monkeypatch):
    home = tmp_path / "state-home"
    home.mkdir()
    monkeypatch.setenv("KG_DIVERGE_HOME", str(home))
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)  # a stray cwd-relative write would land here

    out = _full_round(home, session="sess-A")
    assert out["slate"], "expected a non-empty slate from the round"

    st = State("proj", home=home)
    session_dir = st.session_dir.resolve()

    # every geometry artifact in the whole state home lives under session/
    for p in home.rglob("*"):
        if p.is_file() and p.name in GEOMETRY_FILES:
            assert session_dir in p.resolve().parents, f"I10 violated: {p} outside session scope"
    assert (st.session_dir / "archive.json").exists()

    # and nothing leaked into the working directory
    assert not any(workdir.iterdir()), f"stray files in cwd: {list(workdir.iterdir())}"


def test_i10_new_session_leaves_no_archive_behind(tmp_path, monkeypatch):
    home = tmp_path / "state-home"
    home.mkdir()
    monkeypatch.setenv("KG_DIVERGE_HOME", str(home))

    _full_round(home, session="sess-A")
    st = State("proj", home=home)
    assert st.read_archive().get("niches"), "round must have populated the archive"

    # session boundary: a different id must wipe every geometry artifact
    pipeline.init_project("proj", AXES, seed=3, home=home, session="sess-B")

    survivors = [p for p in home.rglob("*") if p.is_file() and p.name in GEOMETRY_FILES]
    assert not survivors, f"I10 violated: archive artifacts crossed the session boundary: {survivors}"

    st = State("proj", home=home)
    assert st.read_pins("d") == ["c0"]          # durable human signal survives
    assert st.read_discards("d") == ["c1"]      # negative memory survives
    assert st.read_session()["session_id"] == "sess-B"
    assert st.read_axes() is not None


def test_i10_selftest_leaves_no_state_outside_its_temp_home(tmp_path, monkeypatch):
    """The engine selftest provisions its own throwaway home; after it runs, the
    only divergence state anywhere under our controlled HOME/CWD is what WE created."""
    home = tmp_path / "state-home"
    home.mkdir()
    monkeypatch.setenv("KG_DIVERGE_HOME", str(home))
    monkeypatch.chdir(tmp_path)

    from kg_engine.divergence import selftest

    report = selftest.run(project="selftest-i10", seed=0)
    assert report["ok"], {k: report[k] for k in ("ok",) if k in report}
    # the selftest used its own temp home (wiped on exit): ours stayed empty
    assert not any(home.iterdir()), f"selftest leaked into KG_DIVERGE_HOME: {list(home.iterdir())}"
