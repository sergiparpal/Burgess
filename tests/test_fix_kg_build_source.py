"""Regression: /kg-build must resolve the source through the ENGINE, never a shell env var (FALLO 3),
and enumerate a file's sections at its dominant heading level (FALLO 4).

FALLO 3: userConfig options (`source_path`) reach the MCP server process via `.mcp.json`'s
`${user_config.source_path}` → `KG_SOURCE_PATH`, but the host does NOT inject them into the model's Bash
tool shell. The old Step 0 read `${CLAUDE_PLUGIN_OPTION_SOURCE_PATH}` from that shell (always empty) and
silently fell back to `examples/source.md`, ignoring a REQUIRED, configured `source_path`. The engine
already knows the resolved path, so `kg_status()` now exposes it under a `source` block and the command
reads it from there — and fails loud instead of building the demo by surprise.

FALLO 4: the command enumerated only level-2 `## ` headings; a file whose single `## ` is its title but
whose content is `### ` subsections collapsed into one section, breaking span-isolation. Step 0b now
detects the dominant heading level per file and warns on 0-1 level-2 sections.
"""
from pathlib import Path

import pytest

from kg_engine.server import KGEngine

REPO = Path(__file__).resolve().parents[1]
CMD = (REPO / "commands" / "kg-build.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# FALLO 3 — the engine exposes the resolved source through kg_status()
# --------------------------------------------------------------------------- #
def test_kg_status_exposes_resolved_source(engine):
    st = engine.kg_status()
    assert "source" in st, "kg_status must expose the engine-resolved source (FALLO 3)"
    src = st["source"]
    assert src["path"] == str(engine.source_path)     # the path the ENGINE resolved, not a shell env var
    assert src["exists"] is True                       # it resolves to a readable file
    assert "source.md" in src["files"]                 # ...enumerated by basename (R4)


def test_kg_status_source_none_when_unconfigured(vault):
    # No source configured (and no bundled demo under this temp project) → path is None, exists False.
    # The command reads exactly this to STOP instead of silently building examples/source.md.
    pack_path = REPO / "pack" / "pack.yaml"
    eng = KGEngine(vault, source_path=None, pack_path=pack_path)
    src = eng.kg_status()["source"]
    assert src["path"] is None
    assert src["exists"] is False
    assert src["files"] == []


def test_kg_status_source_reports_configured_but_missing_path(vault, tmp_path):
    # A configured path that resolves to zero readable files: path is echoed (so the command can name it)
    # but exists is False — the command STOPs on this rather than falling through to the demo.
    missing = tmp_path / "nope" / "does-not-exist.md"
    eng = KGEngine(vault, source_path=missing, pack_path=REPO / "pack" / "pack.yaml")
    src = eng.kg_status()["source"]
    assert src["path"] == str(missing)
    assert src["exists"] is False
    assert src["files"] == []


# --------------------------------------------------------------------------- #
# FALLO 3 — the command reads the engine, not the shell env var, and fails loud
# --------------------------------------------------------------------------- #
def test_command_does_not_resolve_source_from_shell_env_var():
    # The old silent fallback `SOURCE="${1:-${CLAUDE_PLUGIN_OPTION_SOURCE_PATH:-examples/source.md}}"`
    # must be gone: that env var is empty in the tool shell, so it silently built the demo.
    assert "CLAUDE_PLUGIN_OPTION_SOURCE_PATH:-examples/source.md" not in CMD
    assert 'SOURCE="${1:-${CLAUDE_PLUGIN_OPTION_SOURCE_PATH' not in CMD


def test_command_reads_source_from_kg_status():
    # Step 0a resolves the path through the engine (kg_status().source.path), the single source of truth.
    assert "kg_status()" in CMD
    assert "source.path" in CMD


def test_command_fails_loud_instead_of_demo_fallback():
    # When nothing is configured and no $1 is passed, the command STOPs rather than building the demo.
    assert "STOP" in CMD
    low = CMD.lower()
    assert "fails loud" in low or "fail loud" in low or "silently build" in low


# --------------------------------------------------------------------------- #
# FALLO 4 — dominant heading level detection
# --------------------------------------------------------------------------- #
def test_command_detects_dominant_heading_level():
    # Step 0b must count both `## ` and `### ` and iterate `### ` when a file's only `## ` is its title.
    assert "grep -cE '^## '" in CMD
    assert "grep -cE '^### '" in CMD
    assert "grep -nE '^### '" in CMD          # it actually enumerates the level-3 sections
    low = CMD.lower()
    assert "dominant heading level" in low
    assert "warning" in low                    # warns on 0-1 level-2 sections
