# Donor Baselines (Stage 0, 2026-07-02)

Both donors pinned at these SHAs for the whole build (Decision Rule D5: upstream drift is ignored; re-syncing is a post-release human decision).

## Sproutgraph (convergence donor)

- HEAD: `17c406632bb547a4abca3a824d9ffdc577e83891` (branch `main`)
- Working tree at pin time: clean (`git status --porcelain` empty)
- Test baseline (pristine `git archive` copy, `uv run --extra dev pytest tests/ -p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`):
  - **731 passed, 2 skipped in 45.35s** (733 collected)
  - First run incl. `uv` env sync: 38s wall for the suite portion (cold), 45.35s pytest-reported on the warm rerun.
- 733-vs-496 README discrepancy (plan §2.4): resolved by pytest output — **733 collected** is correct. (The donor's own HEAD commit `17c4066` had already fixed the stale 496 in the README Development section; pytest confirms.)
- Pre-existing failures: none (D4: nothing to grandfather).

## Cambrian (divergence donor)

- HEAD: `a2adfa1d8b83c52ba17a79382811ea82012f8f99` (branch `main`)
- Working tree at pin time: clean
- Test baseline (pristine `git archive` copy; venv via `uv venv` py3.12; `pip install -r skills/ideate/scripts/requirements-dev.txt` + `pip install -e skills/ideate/scripts --no-deps`; `CAMBRIAN_EMBEDDER=hash`, `PYTHONDONTWRITEBYTECODE=1`, `pytest -q -p no:cacheprovider`):
  - **240 passed in 15.67s**
  - Engine correctness contract: `python -m cambrian_engine selftest` → **pass** (~3s wall, hash embedder), all state files written, exit 0.
- Pre-existing failures: none.

## Environment

- Host: WSL2 Linux (kernel 6.6.87.2-microsoft), Python 3.12.3, uv 0.11.23, git 2.43.0.
- Donor suites are hermetic (Cambrian forces `CAMBRIAN_EMBEDDER=hash` + isolated `CAMBRIAN_HOME` in conftest; no model downloads).
