"""Fusion firewall (FUSION_PLAN Stage 2 — written BEFORE the divergence port).

I3 — import firewall: no module on the grounding/verdict/reconciler path may import
     (transitively, over the real module graph) from kg_engine.divergence.
I4 — DB isolation: the derived SQLite the query tools read contains no vector or
     embedding tables/columns; divergence state stays in session scope.
I1/I2 — adversarial, additive to the vendored boundary/reconciler tests: forged
     verdicts and span-less grounded edges are rejected from ANY public write path,
     and the reconciler re-quarantines a hand-forged grounded edge.

These tests pass trivially while kg_engine.divergence does not exist and become
load-bearing the moment it is ported.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from kg_engine.model import EpistemicState, edge_id
from kg_engine.reconciler import Reconciler

REPO = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO / "scripts" / "kg_engine"
DIVERGENCE = "kg_engine.divergence"

# The grounding/verdict/reconciler path per docs/fusion/INVENTORY.md (S1-S4, S12-S13):
# write boundary, verdict audit ledger, reconciler, canon persistence, the data model,
# and the projector that builds the DB kg_query reads. kg_ground itself lives in
# server.py and is covered by the per-function scan below.
VERDICT_PATH_ROOTS = (
    "kg_engine.boundary",
    "kg_engine.groundaudit",
    "kg_engine.reconciler",
    "kg_engine.canon",
    "kg_engine.canonmerge",
    "kg_engine.model",
    "kg_engine.projector",
)

# server.py functions that create or migrate verdicts (INVENTORY S2). No divergence
# import — not even lazy — may appear inside their bodies.
VERDICT_FUNCTIONS = ("kg_ground", "_promote_hypothesis", "_promote_hypothesis_node",
                     "_merge_edge_pair")


def _py_modules() -> dict[str, Path]:
    """Real module map of the kg_engine package (recursive, includes divergence once ported)."""
    mods: dict[str, Path] = {}
    for p in ENGINE_DIR.rglob("*.py"):
        rel = p.relative_to(ENGINE_DIR.parent)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mods[".".join(parts)] = p
    return mods


def _resolve_import(node: ast.AST, modname: str, is_pkg: bool) -> set[str]:
    """Absolute module names referenced by an Import/ImportFrom, resolving relative levels."""
    if isinstance(node, ast.Import):
        return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom):
        if node.level:
            base = modname.split(".")
            anchor = base if is_pkg else base[:-1]
            if node.level > 1:
                anchor = anchor[: len(anchor) - (node.level - 1)]
            prefix = ".".join(anchor)
            mod = f"{prefix}.{node.module}" if node.module else prefix
        else:
            mod = node.module or ""
        return {mod} | {f"{mod}.{a.name}" for a in node.names}
    return set()


def _imports(path: Path, modname: str) -> tuple[set[str], set[str]]:
    """(top-level imports incl. try-guarded, all imports anywhere) for one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    is_pkg = path.name == "__init__.py"
    top: set[str] = set()
    anywhere: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            anywhere |= _resolve_import(node, modname, is_pkg)
    for node in tree.body:
        stack = [node] if isinstance(node, (ast.Import, ast.ImportFrom, ast.Try, ast.If)) else []
        for sub in stack:
            for n in ast.walk(sub):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    top |= _resolve_import(n, modname, is_pkg)
    return top, anywhere


def test_i3_verdict_path_never_reaches_divergence():
    mods = _py_modules()
    for root in VERDICT_PATH_ROOTS:
        assert root in mods, f"verdict-path module {root} missing — update the firewall roots"

    top_graph: dict[str, set[str]] = {}
    lazy: dict[str, set[str]] = {}
    for name, path in mods.items():
        top, anywhere = _imports(path, name)
        top_graph[name] = {i for i in top if i.startswith("kg_engine")}
        lazy[name] = anywhere

    # transitive closure over the REAL top-level import graph from the verdict-path roots
    seen: set[str] = set()
    frontier = list(VERDICT_PATH_ROOTS)
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for dep in top_graph.get(cur, ()):
            dep_mod = dep if dep in top_graph else dep.rsplit(".", 1)[0]
            if dep_mod in top_graph and dep_mod not in seen:
                frontier.append(dep_mod)

    offenders = sorted(m for m in seen if m.startswith(DIVERGENCE))
    assert not offenders, f"I3 violated: verdict path transitively reaches {offenders}"

    # the root modules themselves may not import divergence even lazily
    for root in VERDICT_PATH_ROOTS:
        hits = {i for i in lazy[root] if DIVERGENCE in i}
        assert not hits, f"I3 violated: {root} imports {hits} (lazy imports count here)"


def test_i3_server_verdict_functions_are_divergence_free():
    path = ENGINE_DIR / "server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # no top-level import of divergence in server.py (lazy, flag-guarded use elsewhere is allowed)
    top, _ = _imports(path, "kg_engine.server")
    assert not {i for i in top if DIVERGENCE in i}, "I3: server.py must not import divergence at module top level"

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in VERDICT_FUNCTIONS:
            found.add(node.name)
            for sub in ast.walk(node):
                assert not isinstance(sub, (ast.Import, ast.ImportFrom)) or not any(
                    "divergence" in n for n in _resolve_import(sub, "kg_engine.server", False)
                ), f"I3 violated: {node.name} imports divergence"
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    assert "divergence" not in sub.value, (
                        f"I3 violated: {node.name} references divergence via string {sub.value!r}"
                    )
    assert found == set(VERDICT_FUNCTIONS), f"verdict functions moved? found only {found}"


def test_i3_runtime_grounding_never_loads_divergence(tmp_path):
    """Subprocess probe: a full write->ground cycle must not pull kg_engine.divergence into sys.modules."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "-C", str(proj), "init", "-q"], check=True)
    src = tmp_path / "source.md"
    src.write_text("Degree approximates importance.\n", encoding="utf-8")
    code = f"""
import sys
sys.path.insert(0, {str(REPO / "scripts")!r})
from kg_engine.server import KGEngine
eng = KGEngine({str(proj)!r}, source_path={str(src)!r}, pack_path={str(REPO / "pack" / "pack.yaml")!r})
out = eng.kg_write({{"edges": [{{"source": "degree", "target": "importance",
                    "relation": "approximates", "span": "Degree approximates importance."}}]}})
assert out["dispositions"]["ACCEPTED"] == 1, out
from kg_engine.model import edge_id
g = eng.kg_ground(edge_id("degree", "approximates", "importance"), "grounded", by="agent")
assert g.get("ok"), g
bad = [m for m in sys.modules if m.startswith("kg_engine.divergence")]
assert not bad, f"I3 violated at runtime: {{bad}}"
print("RUNTIME-FIREWALL-OK")
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "RUNTIME-FIREWALL-OK" in r.stdout, r.stderr[-2000:]


_FORBIDDEN_SCHEMA = re.compile(r"vec|vss|embed|faiss|vector", re.IGNORECASE)


def test_i4_query_db_has_no_vector_schema(engine):
    engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance"}]})
    engine.query_graph()  # forces projection of the derived layer

    db = engine.data_dir / "derived" / "index.sqlite"
    assert db.exists(), "derived index.sqlite missing after projection"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        objects = con.execute(
            "SELECT type, name, COALESCE(sql,'') FROM sqlite_master").fetchall()
        assert objects, "empty schema?"
        for typ, name, ddl in objects:
            assert not _FORBIDDEN_SCHEMA.search(name), f"I4 violated: {typ} {name!r}"
            assert not _FORBIDDEN_SCHEMA.search(ddl), f"I4 violated: {typ} {name!r} DDL: {ddl}"
        for (tbl,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            for col in con.execute(f"PRAGMA table_info({tbl})").fetchall():
                assert not _FORBIDDEN_SCHEMA.search(col[1]), f"I4 violated: {tbl}.{col[1]}"
    finally:
        con.close()


def test_i4_divergence_state_is_session_scoped(tmp_path, monkeypatch):
    """Pre-port: the divergence package must simply not exist. Post-port: its state
    resolver must target the project-local session dir (.kg/diverge) or an explicit
    override — never the canon vault or the derived DB directory."""
    # The Stage-2 port has landed, so kg_engine.divergence MUST resolve. The old pre-port guard
    # (`assert True; return`) would now SILENTLY pass on a package-resolution regression — the exact
    # failure this test exists to catch (review-r4: firewall-guard-vacuous-pass).
    assert importlib.util.find_spec("kg_engine.divergence") is not None, \
        "kg_engine.divergence failed to resolve — a packaging regression, not a pre-port state"

    from kg_engine.divergence import state as dstate

    monkeypatch.delenv("KG_DIVERGE_HOME", raising=False)
    monkeypatch.setenv("KG_PROJECT_DIR", str(tmp_path))
    base = Path(dstate.base_dir())
    assert base == tmp_path / ".kg" / "diverge", f"I4: default state home escaped session scope: {base}"

    override = tmp_path / "custom-home"
    monkeypatch.setenv("KG_DIVERGE_HOME", str(override))
    assert Path(dstate.base_dir()) == override


def _single_detail(out: dict, disposition: str) -> dict:
    hits = [d for d in out["details"] if d["disposition"] == disposition]
    assert hits, f"expected a {disposition} item: {json.dumps(out)[:400]}"
    return hits[0]


def test_i1_write_cannot_forge_grounded_even_with_valid_span(engine):
    out = engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance", "epistemic_state": "grounded"}]})
    d = _single_detail(out, "DEMOTED")
    assert "forged-verdict-stripped" in d["reason"]
    node = engine.canon.read_node("degree")
    e = next(e for e in node.edges if e.id == d["id"])
    assert e.epistemic_state is EpistemicState.UNVERIFIED


def test_i1_propose_lane_strips_claimed_verdicts(engine):
    out = engine.kg_propose({"edges": [
        {"source": "degree", "target": "importance", "relation": "bridges",
         "epistemic_state": "grounded"}]})
    d = _single_detail(out, "DEMOTED")
    assert "forged-verdict-stripped" in d["reason"]
    node = engine.canon.read_node("degree")
    e = next(e for e in node.edges if e.id == d["id"])
    assert e.epistemic_state is EpistemicState.UNVERIFIED
    assert e.provenance.value == "hypothesized" and e.span == ""


def test_i2_spanless_grounded_write_is_rejected_and_absent(engine):
    out = engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "epistemic_state": "grounded"}]})
    d = _single_detail(out, "REJECTED")
    assert "no-supporting-span" in d["reason"]
    try:
        node = engine.canon.read_node("degree")
    except FileNotFoundError:
        node = None  # nothing was written at all — the strongest form of absence
    assert node is None or all(e.id != d["id"] for e in node.edges)


def test_i2_reconciler_requarantines_hand_forged_grounded(engine):
    engine.kg_write({"edges": [
        {"source": "degree", "target": "importance", "relation": "approximates",
         "span": "Degree approximates importance"}]})
    eid = edge_id("degree", "approximates", "importance")
    recon = Reconciler(engine.canon)
    recon.scan(full_sweep=True)  # record the honest unverified baseline

    node = engine.canon.read_node("degree")
    edge = next(e for e in node.edges if e.id == eid)
    edge.epistemic_state = EpistemicState.GROUNDED  # forge: no kg_ground, no audit record
    edge.verdict_by = "human"
    engine.canon.write_one(node)

    report = recon.scan(full_sweep=True)
    assert eid in report.requarantined, f"forgery survived: {report}"
    node = engine.canon.read_node("degree")
    edge = next(e for e in node.edges if e.id == eid)
    assert edge.epistemic_state is EpistemicState.UNVERIFIED
    assert not edge.verdict_by and not edge.verdict_at
