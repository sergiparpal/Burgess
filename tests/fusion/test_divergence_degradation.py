"""I9 — graceful degradation (FUSION_PLAN Stage 2).

If the embedding model or the divergence deps are unavailable (offline, blocked,
uninstalled), divergence features fail with a clear actionable message and every
convergence capability works untouched.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from kg_engine.divergence.config import ConfigError
from kg_engine.divergence.embed import HashingEmbedder, StaticEmbedder

REPO = Path(__file__).resolve().parents[2]


def test_missing_model2vec_raises_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "model2vec", None)  # simulate not installed
    emb = StaticEmbedder()
    with pytest.raises(ConfigError) as exc:
        emb.embed(["one idea"])
    msg = str(exc.value)
    assert "model2vec" in msg and "KG_DIVERGE_EMBEDDER=hash" in msg
    assert "kg_*" in msg  # says convergence is unaffected


def test_model_download_failure_raises_actionable_error(monkeypatch):
    class _Boom:
        @staticmethod
        def from_pretrained(name):
            raise OSError("connection refused: huggingface.co")

    import types
    fake = types.ModuleType("model2vec")
    fake.StaticModel = _Boom
    monkeypatch.setitem(sys.modules, "model2vec", fake)
    emb = StaticEmbedder()
    with pytest.raises(ConfigError) as exc:
        emb.embed(["one idea"])
    msg = str(exc.value)
    assert "could not load model" in msg and "KG_DIVERGE_EMBEDDER=hash" in msg


def test_hash_embedder_needs_no_model(monkeypatch):
    monkeypatch.setitem(sys.modules, "model2vec", None)
    vecs = HashingEmbedder().embed(["idea one", "a very different idea"])
    assert vecs.shape[0] == 2 and vecs.shape[1] == 512


def test_core_engine_works_with_divergence_deps_blocked(tmp_path):
    """The full convergence round-trip must succeed in a process where numpy,
    scikit-learn and model2vec cannot even be imported (I9's strongest form)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "-C", str(proj), "init", "-q"], check=True)
    src = tmp_path / "source.md"
    src.write_text("Degree approximates importance.\n", encoding="utf-8")
    code = f"""
import sys
sys.path.insert(0, {str(REPO / "scripts")!r})

import builtins
_real_import = builtins.__import__
BLOCKED = ("numpy", "sklearn", "scipy", "model2vec")
def _guard(name, *a, **k):
    if name.split(".")[0] in BLOCKED:
        raise ImportError(f"blocked for I9 test: {{name}}")
    return _real_import(name, *a, **k)
builtins.__import__ = _guard

from kg_engine.server import KGEngine
from kg_engine.model import edge_id
eng = KGEngine({str(proj)!r}, source_path={str(src)!r}, pack_path={str(REPO / "pack" / "pack.yaml")!r})
out = eng.kg_write({{"edges": [{{"source": "degree", "target": "importance",
                    "relation": "approximates", "span": "Degree approximates importance."}}]}})
assert out["dispositions"]["ACCEPTED"] == 1, out
g = eng.kg_ground(edge_id("degree", "approximates", "importance"), "grounded", by="agent")
assert g.get("ok"), g
q = eng.query_graph(relation="approximates")
assert any(e["epistemic_state"] == "grounded" for e in q.get("edges") or q.get("results") or []), q
ctx = eng.projector.kg_context()
assert "falsification_counters" in ctx, sorted(ctx)
print("CORE-OK-WITHOUT-DIVERGENCE-DEPS")
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0 and "CORE-OK-WITHOUT-DIVERGENCE-DEPS" in r.stdout, r.stderr[-3000:]
