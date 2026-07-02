"""Shared pytest fixtures.

Tests are hermetic: state goes to a temp dir (via ``KG_DIVERGE_HOME``)
and embeddings use the deterministic hashing embedder (via
``KG_DIVERGE_EMBEDDER=hash``) so no model is ever downloaded.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _hash_embedder(monkeypatch, tmp_path):
    """Force the deterministic embedder and an isolated default state home.

    Burgess's ``base_dir()`` is project-local (``<cwd>/.kg/diverge`` when
    ``KG_PROJECT_DIR`` is unset), so a test that forgets the ``home`` fixture
    would otherwise write into the repo working tree. The autouse default home
    keeps every test hermetic; the explicit ``home`` fixture below still wins
    because it overwrites the same env var."""
    monkeypatch.setenv("KG_DIVERGE_EMBEDDER", "hash")
    monkeypatch.delenv("KG_PROJECT_DIR", raising=False)
    monkeypatch.setenv("KG_DIVERGE_HOME", str(tmp_path / "default-state-home"))


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """An isolated state home for one test."""
    h = tmp_path / "state-home"
    h.mkdir()
    monkeypatch.setenv("KG_DIVERGE_HOME", str(h))
    return h
