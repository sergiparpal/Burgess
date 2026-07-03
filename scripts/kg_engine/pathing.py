"""Grounded-path explanation (§2): the pure algorithm behind ``kg_explain_path``.

Extracted from the KGEngine facade in review-r5 — it was the one large inline algorithm there
(~130 lines with three nested functions), which made it untestable in isolation and buried the
facade's actual job (wiring + egress policy). Everything here is a pure function of the derived
graph: no engine, no scrubbing, no degraded-flag folding — the facade applies those to the result.

Determinism is load-bearing throughout (G6): sorted-neighbour BFS, a (distance, id) total order for
the nearest-neighbour walk, and smallest-edge-id representative selection make the output byte-stable
across processes — unlike ``networkx.greedy_tsp``, whose internal ``min(set(...))`` tie-breaks on
hash-randomized set iteration order (a real hazard here: the grounded closure's unit-weight
distances tie pervasively and server restarts are routine).
"""
from __future__ import annotations

import itertools
from collections import deque

import networkx as nx

from .model import EpistemicState


def grounded_view(G) -> nx.Graph:
    """The grounded-ONLY undirected view: an undirected pair {u,v} exists iff at least one parallel
    edge between them (either direction) is ``epistemic_state == grounded``. Carries ONE
    representative grounded edge's relation+span — deterministically the smallest edge id — for the
    audit trail. unverified / hypothesized / failed / rejected edges are excluded ENTIRELY: routing
    a chain through them would manufacture a false "explanation", defeating the auditability
    purpose (§2)."""
    Gg = nx.Graph()
    Gg.add_nodes_from(G.nodes())
    reps: dict = {}  # frozenset({u,v}) -> (edge_id, relation, span) representative grounded edge
    for u, v, d in G.edges(data=True):
        if u == v or d.get("epistemic_state") != EpistemicState.GROUNDED.value:
            continue
        key = frozenset((u, v))
        eid = d.get("id", "") or ""
        prior = reps.get(key)
        if prior is None or eid < prior[0]:
            reps[key] = (eid, d.get("relation", "") or "", d.get("span", "") or "")
    for key, (_eid, rel, span) in reps.items():
        a, b = sorted(key)
        Gg.add_edge(a, b, relation=rel, span=span)
    return Gg


def _grounded_path(Gg: nx.Graph, s, t):
    """Deterministic shortest path s->t over Gg (sorted-neighbour predecessor BFS); None when no
    fully-grounded path exists."""
    if s == t:
        return [s]
    if s not in Gg or t not in Gg:
        return None
    pred = {s: s}
    q = deque([s])
    while q:
        cur = q.popleft()
        for nb in sorted(Gg.neighbors(cur)):  # sorted -> byte-stable path among equal-length ties
            if nb in pred:
                continue
            pred[nb] = cur
            if nb == t:
                path = [t]
                while path[-1] != s:
                    path.append(pred[path[-1]])
                path.reverse()
                return path
            q.append(nb)
    return None


def _unreachable(reason: str) -> dict:
    return {"path": [], "edges": [], "leap": None, "grounded_only": True, "reason": reason}


def explain_grounded_path(G, nodes) -> dict:
    """Trace the associative chain connecting ``nodes`` over GROUNDED edges only.

    Returns the ordered node ``path``, the grounded ``edges`` used (relation + span, for audit),
    and an ADVISORY ``leap`` = the path edge-count — never a verdict, never written, never folded
    into a score (G1/G4). For >2 nodes the visiting order comes from a deterministic
    nearest-neighbour walk (a TSP-path approximation) over the grounded shortest-path closure.
    EMPTY (path=[], leap=null) with a ``reason`` when no fully-grounded path exists — itself
    informative: the concepts are joined only through unverified/hypothesized/refuted links, or
    not at all."""
    Gg = grounded_view(G)

    uniq = sorted(set(str(n) for n in (nodes or [])))
    if not uniq:
        return _unreachable("no nodes requested")
    missing = [n for n in uniq if n not in Gg]
    if missing:
        return _unreachable(f"node not in graph: {missing[0]}")
    if len(uniq) == 1:
        return {"path": [uniq[0]], "edges": [], "leap": 0, "grounded_only": True}

    # cache oriented grounded shortest paths between requested concepts (the BFS is deterministic).
    seg_cache: dict = {}

    def _seg(a, b):
        if (a, b) not in seg_cache:
            p = _grounded_path(Gg, a, b)
            seg_cache[(a, b)] = p
            if p is not None:
                seg_cache[(b, a)] = list(reversed(p))
        return seg_cache[(a, b)]

    if len(uniq) == 2:
        full = _seg(uniq[0], uniq[1])
        if full is None:
            return _unreachable(f"no fully-grounded path between {uniq[0]} and {uniq[1]}")
    else:
        # every requested concept must be mutually reachable over grounded edges; report the FIRST
        # offending pair (combinations of the sorted set -> deterministic). Build the metric closure.
        dist: dict = {}
        for a, b in itertools.combinations(uniq, 2):
            seg = _seg(a, b)
            if seg is None:
                return _unreachable(f"no fully-grounded path between {a} and {b}")
            dist[(a, b)] = dist[(b, a)] = len(seg) - 1
        # deterministic nearest-neighbour walk (see the module docstring for why not greedy_tsp):
        # start at the smallest id, repeatedly take the closest unvisited concept, ties by id.
        order = [uniq[0]]
        remaining = set(uniq[1:])
        while remaining:
            cur = order[-1]
            nxt = min(remaining, key=lambda n: (dist[(cur, n)], n))
            order.append(nxt)
            remaining.discard(nxt)
        full = []
        for a, b in zip(order, order[1:]):
            seg = _seg(a, b)
            full += seg if not full else seg[1:]

    # collect the grounded edges along the full chain (relation+span per hop, for audit). Every
    # consecutive pair is a Gg edge by construction; guard defensively all the same.
    edges_used = []
    for a, b in zip(full, full[1:]):
        d = Gg.get_edge_data(a, b)
        if d is None:
            return _unreachable(f"no fully-grounded path between {a} and {b}")
        edges_used.append({"source": a, "target": b,
                           "relation": d.get("relation", ""), "span": d.get("span", "")})
    return {"path": full, "edges": edges_used, "leap": len(edges_used), "grounded_only": True}
