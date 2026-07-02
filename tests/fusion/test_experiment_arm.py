"""Stage 6 — the graph+generate+dpp experiment arm (FUSION_PLAN §13).

The vendored harness is arm-tolerant; these tests pin the new arm's canonical
position and the dedicated dpp_verdict (the D1 comparison surface).
"""
from __future__ import annotations

from kg_engine.harness import _CANONICAL_ARMS, ideation

SOURCE = ("entropy grounds the arrow of time. betweenness measures bridges. "
          "compression predicts observations. falsification defends against failures. "
          "provenance carries spans. communities connect through genuine bridges.")


def _ideas(diverse: bool) -> list[str]:
    if diverse:
        return [
            "Because compression predicts observations, a bridge between communities earns trust.",
            "Falsification defends against failures, therefore betweenness needs provenance spans.",
            "If provenance carries spans, genuine bridges connect communities because entropy grounds order.",
        ]
    return [
        "entropy grounds the arrow of time in the graph.",
        "entropy grounds the arrow of time for bridges.",
        "entropy grounds the arrow of time again.",
    ]


def test_arm_is_canonical_and_ordered_after_graph_generate():
    assert "graph+generate+dpp" in _CANONICAL_ARMS
    assert _CANONICAL_ARMS.index("graph+generate+dpp") == _CANONICAL_ARMS.index("graph+generate") + 1


def test_dpp_verdict_present_and_directional():
    out = ideation({"control": _ideas(False), "graph": _ideas(True),
                    "graph+generate": _ideas(False), "graph+generate+dpp": _ideas(True)},
                   source_text=SOURCE)
    assert list(out["table"])[:4] == ["control", "graph", "graph+generate", "graph+generate+dpp"]
    assert out["dpp_verdict"].startswith("graph+generate+dpp beat graph+generate")

    flipped = ideation({"graph+generate": _ideas(True), "graph+generate+dpp": _ideas(False)},
                       source_text=SOURCE)
    assert "did NOT clearly beat" in flipped["dpp_verdict"]


def test_dpp_verdict_absent_when_arm_missing():
    out = ideation({"control": _ideas(False), "graph": _ideas(True)}, source_text=SOURCE)
    assert "dpp_verdict" not in out
