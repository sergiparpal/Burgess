"""Burgess divergence engine (ported from Cambrian, firewalled below grounding).

Deterministic, domain-agnostic diversity engine that owns the anti-convergence
math for the `/kg-diverge` flow: embeddings, MAP-Elites archive, geometric
novelty, DPP diverse selection, an anti-collapse monitor, and local preference
memory.

The LLM parts (variation operators, the skeptical judge prefilter) are performed
by the agent, not here. This package never judges novelty: geometry owns
diversity, the judge only filters validity/on-brief upstream.

Fusion invariants (FUSION_PLAN §4): nothing in this package can set or upgrade
an epistemic state (I1), no grounding/verdict/reconciler module may import it
(I3, firewall-tested), its vectors never touch canon or the query DB (I4), and
everything it computes is advisory — embeddings measure dispersion, never truth
(I5).
"""

__version__ = "0.2.3"
