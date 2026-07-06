"""Regression: a `source_path` wrapped in quotes must not carry literal quotes into the engine.

The `source_path` userConfig value reaches the engine via `KG_SOURCE_PATH` and the `/kg-build` bash
via `CLAUDE_PLUGIN_OPTION_SOURCE_PATH`. When the user wraps the path in quotes (or a host hands the
value back JSON-quoted), the substituted env value keeps the literal surrounding quotes — so
`Path('"C:\\x"')` points nowhere and the engine silently degrades to an empty source. The canonical
env-value cleaner now strips ONE matched surrounding pair; these pin that and its JS mirror.
"""
from pathlib import Path
import re

import pytest

from kg_engine import envconfig


REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("raw,expected", [
    ('"C:\\docs\\source.md"', "C:\\docs\\source.md"),   # double-quoted Windows path
    ("'/home/u/source.md'", "/home/u/source.md"),        # single-quoted POSIX path
    ('  "/a/b.md"  ', "/a/b.md"),                          # surrounding whitespace + quotes
    ('"  /a/b.md  "', "/a/b.md"),                          # whitespace INSIDE the quotes
    ("/a/b.md", "/a/b.md"),                                # bare path untouched
    ('""C:\\d\\s.md""', "C:\\d\\s.md"),                   # DOUBLE double-quotes -> bare path
    ('""""/a/b.md""""', "/a/b.md"),                        # four-deep wrapping still collapses
    ('"\'/a/b.md\'"', "/a/b.md"),                          # mixed nested pairs (double outside single)
])
def test_clean_strips_all_matched_quote_pairs(raw, expected):
    assert envconfig.clean(raw) == expected


@pytest.mark.parametrize("raw", [
    'C:\\has"quote.md',      # an unmatched interior quote is part of the path — do NOT strip
    "'mismatched\"",          # first/last quotes differ — not a matched pair
    '"',                       # a lone quote is not a pair (len < 2 after the pair check)
])
def test_clean_leaves_unmatched_quotes_intact(raw):
    assert envconfig.clean(raw) == raw.strip()


def test_dequote_then_sentinel_filter_still_fires():
    # A quoted placeholder / venv sentinel must still be dropped after dequoting (dequote runs first).
    assert envconfig.clean('"${user_config.source_path}"') == ""
    assert envconfig.clean('"/.venv"') == ""


def test_resolve_source_dequotes_env_path(monkeypatch, tmp_path):
    """The quoted path resolves to the real, existing file — not a phantom quote-wrapped path."""
    src = tmp_path / "source.md"
    src.write_text("x", encoding="utf-8")
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_SOURCE_PATH", raising=False)
    monkeypatch.setenv("KG_SOURCE_PATH", f'"{src}"')
    resolved = envconfig.resolve_source(tmp_path)
    assert resolved == str(src)
    assert Path(resolved).exists()


def test_resolve_source_dequotes_plugin_option(monkeypatch, tmp_path):
    """The userConfig read (CLAUDE_PLUGIN_OPTION_SOURCE_PATH) is dequoted too, and wins over env."""
    src = tmp_path / "s.md"
    src.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_SOURCE_PATH", f"'{src}'")
    monkeypatch.delenv("KG_SOURCE_PATH", raising=False)
    assert envconfig.resolve_source(tmp_path) == str(src)


def test_js_mirror_dequotes_in_clean():
    """§2.3 source-grep parity (Node isn't guaranteed in CI): the JS twin must define `dequote` and
    apply it inside `clean`, matching kg_engine.envconfig. Keeps the two cleaners in lockstep."""
    js = (REPO / "scripts" / "_engine_resolve.mjs").read_text(encoding="utf-8")
    assert "function dequote(" in js, "JS mirror lost its dequote helper"
    assert re.search(r"const v = dequote\(value\.trim\(\)\)", js), \
        "JS clean() must dequote the trimmed value before the sentinel filter"
