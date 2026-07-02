"""Advisory DPP geometry over /kg-generate candidates (FUSION_PLAN Stage 5).

Behind the ``divergence.dpp`` pack flag (default OFF), the seven structural
mechanisms' candidates get Cambrian's diversity discipline before presentation:

    candidates -> embed -> HYBRID descriptors (one semantic axis + graph-
    structural axes) -> MAP-Elites binning (in memory only, I10) -> DPP
    ordering (judge-bounded quality, I6 constants) -> same set, diverse order.

Everything here is ADVISORY (I5): it reorders and annotates what is proposed —
it never adds, drops, or mutates a candidate, never touches scores the
grounding queue uses, and nothing downstream of kg_propose can see the
difference. Embeddings measure dispersion, never truth.

Design intuition (plan Stage 5.3): the periphery mechanism and cliché-distance
are two views of the same away-from-center pressure. Periphery walks away from
the graph's STRUCTURAL center (the high-degree grounded hubs); the hybrid
cliché map takes those same hubs' labels as the SEMANTIC center and measures
each candidate's embedding distance from them. A candidate can therefore be
"peripheral" structurally, semantically, or both — the hybrid descriptors keep
the two pressures visible as separate axes instead of collapsing them.

This module is imported LAZILY by the generate path only (I3: the verdict path
never reaches it) and degrades gracefully (I9: any failure keeps the donor
ordering and reports why).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# The brief-level cliché map enumerates ~6 obvious answers; the graph-level map
# mirrors that size with the top grounded hubs (the graph's "center").
DEFAULT_TOP_HUBS = 6
# Risk-register cap: above this, skip the DPP kernel and fall back to
# novelty-only ordering (still advisory, still the same candidate set).
DEFAULT_POOL_CAP = 200


def pack_dpp_default(pack) -> bool:
    """The divergence.dpp flag from the loaded pack (default OFF; Stage 6's
    pre-declared rule D1 may flip the shipped default)."""
    try:
        section = getattr(pack, "divergence", None) or {}
        return bool(section.get("dpp", False))
    except AttributeError:
        return False


def _candidate_text(c: Dict[str, Any]) -> str:
    if c.get("kind") == "node" or c.get("label"):
        return f"{c.get('label', '')} ({c.get('mechanism', '')})".strip()
    return (f"{c.get('source', '')} {c.get('relation', '')} {c.get('target', '')} "
            f"({c.get('mechanism', '')})").strip()


def _grounded_hubs(G, k: int) -> List[Tuple[str, str]]:
    """Top-k nodes by GROUNDED-degree (fallback: total degree) — the graph's center."""
    counts: Dict[str, int] = {}
    for u, v, data in G.edges(data=True):
        if (data or {}).get("epistemic_state") == "grounded":
            counts[u] = counts.get(u, 0) + 1
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        counts = {n: int(d) for n, d in G.degree()}
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return [(n, str(G.nodes[n].get("label", n))) for n, _ in top]


def _structural_descriptor(c: Dict[str, Any], G, undirected, dist_cache: Dict) -> Dict[str, Any]:
    """Cheap graph-structural axes, all read straight off the derived graph."""
    if c.get("kind") == "node" or not c.get("source"):
        return {"community": "node", "graph_distance": "node", "grounded_mix": 0.0}
    u, v = c.get("source"), c.get("target")
    cu = G.nodes[u].get("community") if u in G else None
    cv = G.nodes[v].get("community") if v in G else None
    if cu is None or cv is None:
        community = "unknown"
    else:
        community = "intra" if cu == cv else "cross"

    key = (u, v) if u <= v else (v, u)
    if key not in dist_cache:
        try:
            import networkx as nx
            dist_cache[key] = nx.shortest_path_length(undirected, u, v)
        except Exception:  # noqa: BLE001 — disconnected/missing endpoints: maximal distance
            dist_cache[key] = None
    d = dist_cache[key]
    graph_distance = "unreachable" if d is None else ("d" + str(min(int(d), 5)))

    incident_states = [
        (data or {}).get("epistemic_state") == "grounded"
        for node in (u, v) if node in G
        for _, _, data in G.edges(node, data=True)
    ]
    grounded_mix = (sum(incident_states) / len(incident_states)) if incident_states else 0.0
    return {"community": community, "graph_distance": graph_distance,
            "grounded_mix": round(float(grounded_mix), 4)}


def order_candidates(
    candidates: List[Dict[str, Any]],
    G,
    seed: int = 0,
    top_hubs: int = DEFAULT_TOP_HUBS,
    pool_cap: int = DEFAULT_POOL_CAP,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (same candidates diversely reordered, advisory block).

    The advisory block carries the hybrid bins, per-candidate semantic novelty
    and cliché distance, and the hub cliché map — presentation labels for the
    /kg-generate slate, mirroring /kg-diverge's. Candidates beyond ``pool_cap``
    keep their donor (score-ranked) order after the geometric prefix.
    """
    n = len(candidates)
    if n < 2:
        return list(candidates), {"applied": False, "reason": "fewer than 2 candidates"}

    import numpy as np

    from .divergence import archive as darchive
    from .divergence import config as dconfig
    from .divergence import diversity as ddiv
    from .divergence import novelty as dnov
    from .divergence import originality as dorig
    from .divergence.embed import get_embedder
    from .divergence.pipeline import QUALITY_WEIGHT

    pool = candidates[:pool_cap]
    rest = candidates[pool_cap:]
    texts = [_candidate_text(c) for c in pool]
    emb = get_embedder()
    vecs = np.asarray(emb.embed(texts), dtype=np.float64)

    # one SEMANTIC axis: batch k-NN novelty (dispersion within this round)
    semantic = dnov.knn_novelty(vecs, vecs, k=min(5, len(pool) - 1), exclude_self=True)

    # hybrid cliché map: the grounded hubs are the graph's center
    hubs = _grounded_hubs(G, top_hubs)
    if hubs:
        hub_vecs = np.asarray(emb.embed([label for _, label in hubs]), dtype=np.float64)
        cliche = dorig.originality_scores(vecs, hub_vecs)["per_idea"]
    else:
        cliche = [0.0] * len(pool)

    # graph-structural axes off the derived graph (cheap, precomputed data)
    undirected = G.to_undirected(as_view=True)
    dist_cache: Dict = {}
    spec = dconfig.axes_spec_from_dict({
        "domain": "generate-advisory",
        "unit_of_generation": "candidate",
        "axes": [
            {"name": "semantic_novelty", "type": "continuous", "range": [0.0, 2.0]},
            {"name": "community", "type": "categorical"},
            {"name": "graph_distance", "type": "categorical"},
            {"name": "grounded_mix", "type": "continuous", "range": [0.0, 1.0]},
        ],
    })
    bins: List[str] = []
    for i, c in enumerate(pool):
        descriptor = {"semantic_novelty": float(semantic[i]),
                      **_structural_descriptor(c, G, undirected, dist_cache)}
        nid, _coords = darchive.compute_niche(descriptor, spec, {})
        bins.append(nid)

    # DPP ordering with judge-bounded quality (I6 constants preserved verbatim)
    scores = np.asarray([float(c.get("score", 0.0)) for c in pool], dtype=np.float64)
    order = ddiv.select_diverse(vecs, k=max(1, len(pool) - 1), quality=scores,
                                seed=seed, quality_weight=QUALITY_WEIGHT)
    order += [i for i in range(len(pool)) if i not in set(order)]

    ordered = [pool[i] for i in order] + list(rest)
    advisory = {
        "applied": True,
        "order": "dpp",
        "axes": ["semantic_novelty", "community", "graph_distance", "grounded_mix"],
        "bins": [bins[i] for i in order],
        "semantic_novelty": [round(float(semantic[i]), 4) for i in order],
        "cliche_distance": [round(float(cliche[i]), 4) for i in order],
        "cliche_hubs": [n for n, _ in hubs],
        "pool": len(pool),
        "beyond_cap_kept_in_donor_order": len(rest),
        "note": ("advisory ordering + labels only (I5): same candidate set, no score "
                 "changes, nothing downstream of kg_propose can see the difference"),
    }
    return ordered, advisory
