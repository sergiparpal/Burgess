"""File-based local state for a divergence project (FUSION_PLAN Stage 2/3).

State is **project-local and git-friendly**: the base directory is
``<project>/.kg/diverge`` (project root = ``KG_PROJECT_DIR``, else the cwd),
overridable with the ``KG_DIVERGE_HOME`` environment variable (used by the
test suite to isolate runs). Explicitly not the donor's ``~/.cambrian``.

Geometry state is **session-ephemeral (invariant I10)**: the MAP-Elites
archive and everything derived from embeddings live under ``session/`` and
are wiped when a new session begins (``begin_session``). Only pins, discards,
comparisons, and project/session metadata are durable — in the fused plugin
the knowledge graph, not the archive, is the durable memory. Layout::

    <home>/<project-slug>/
        meta.json                 # project metadata              (durable)
        axes.json                 # snapshot of the resolved axes (durable)
        session.json              # active session id + start    (durable)
        session/                  # I10: wiped on session change
            archive.json          # MAP-Elites: niche_id -> niche record
            candidates.json       # id -> candidate record (genealogy kept)
            embeddings.json       # id -> embedding vector
            mech_embeddings.json  # id -> mechanism-axis embedding
            open_nicher.json      # open-axis Voronoi partition
        tmp/                      # scratch dir for the skill's hand-off files
        memory/<domain>/
            comparisons.jsonl     # appended preference events   (durable)
            pins.json             # pinned "stepping stone" ids  (durable)
            discards.json         # negative memory              (durable)

Preferences are namespaced per domain so switching domains keeps memories
separate.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ConfigError

_log = logging.getLogger(__name__)

DEFAULT_HOME_ENV = "KG_DIVERGE_HOME"
PROJECT_DIR_ENV = "KG_PROJECT_DIR"

_PATH_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Best-effort cross-process lock (atomic mkdir works on every target OS) used to
# serialize read-modify-write on the small per-domain files (pins). Tuned for the
# realistic "two /ideate sessions on one project" race, not high contention.
_LOCK_TIMEOUT = 10.0   # seconds to wait for the lock before proceeding anyway
_LOCK_STALE = 60.0     # a lock dir older than this is assumed abandoned (crash)
_LOCK_POLL = 0.05
# Orphaned atomic-write temp files older than this are swept on State.ensure().
_STALE_TEMP_SECS = 3600.0


def _path_slug(name: str, fallback: str = "default") -> str:
    """Filesystem-safe slug for a project or domain id.

    A name that is already a valid slug round-trips unchanged, so existing state
    dirs (the common case: plain ASCII ids) are preserved exactly. When slugging is
    *lossy* — characters were replaced/stripped, or a non-ASCII-only id reduces to
    ``fallback`` — distinct names could otherwise collide on one slug and silently
    merge state (e.g. every non-ASCII id -> ``"default"``, or ``"proj A"`` and
    ``"proj-A"`` -> the same dir). In that case we append a short hash of the raw
    name so different ids can never share a directory.
    """
    raw = str(name)
    s = _PATH_SLUG_RE.sub("-", raw.strip()).strip("-_.")
    if s == raw:
        return s  # already a clean slug: unchanged, backward-compatible
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{s or fallback}-{suffix}"


def base_dir() -> Path:
    """Project-local state home: ``<project>/.kg/diverge`` unless overridden.

    ``KG_DIVERGE_HOME`` (tests, power users) wins; else the project root comes
    from ``KG_PROJECT_DIR`` (set for the MCP server by .mcp.json) or the cwd.
    """
    env = os.environ.get(DEFAULT_HOME_ENV)
    if env:
        return Path(env).expanduser()
    project = os.environ.get(PROJECT_DIR_ENV) or os.getcwd()
    return Path(project).expanduser() / ".kg" / "diverge"


def _fsync_dir(directory: Path) -> None:
    """Best-effort fsync of a directory so a rename is durable across a crash.

    ``os.fsync`` on the file only flushes its *contents*; the directory entry that
    ``os.replace`` creates is separate metadata and can be lost on power loss even
    though the data was synced. Fsyncing the parent closes that gap on POSIX. A
    no-op where a directory handle can't be fsynced (e.g. Windows has no
    ``O_DIRECTORY`` and raises on fsync of a dir fd).
    """
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        dfd = os.open(str(directory), os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(dfd)
    except OSError:
        pass
    finally:
        os.close(dfd)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            # Flush + fsync before the rename so a crash can't persist the rename
            # ahead of the data (which would leave a zero-length/stale file).
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        # Fsync the directory so the rename itself is durable, not just the data.
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _steal_stale_lock(lock: Path) -> None:
    """Atomically reclaim a presumed-abandoned lock dir.

    ``os.replace`` of a directory is atomic, so exactly one racer wins the rename
    and removes it; the losers get an ``OSError`` and simply re-attempt the
    ``mkdir``. This avoids the stat-then-``rmdir`` TOCTOU where two processes both
    observe the lock as stale, both delete it, and both proceed — one possibly
    deleting a *fresh* lock a third process just created.
    """
    sidelined = lock.with_name(f"{lock.name}.stale-{os.getpid()}")
    try:
        os.replace(lock, sidelined)
    except OSError:
        return  # another racer won the steal (or it vanished); just retry mkdir
    shutil.rmtree(sidelined, ignore_errors=True)


@contextlib.contextmanager
def _file_lock(target: Path, timeout: float = _LOCK_TIMEOUT):
    """Best-effort cross-process lock guarding a read-modify-write on ``target``.

    Uses an atomic ``mkdir`` of a sibling ``<name>.lock`` directory (atomic on
    POSIX and Windows). Steals a lock older than ``_LOCK_STALE`` (a crashed
    holder). If the lock can't be acquired within ``timeout`` we proceed anyway
    rather than deadlock — the protected section is then no worse than the
    historical unlocked behavior (and is logged at WARNING for diagnosis).
    """
    lock = target.parent / (target.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, timeout)
    acquired = False
    while True:
        try:
            lock.mkdir()
            acquired = True
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0.0
            if age > _LOCK_STALE:
                _steal_stale_lock(lock)
                continue
            if time.monotonic() >= deadline:
                _log.warning("lock not acquired within %.1fs; proceeding "
                             "unlocked on %s", timeout, target)
                break  # give up; proceed unlocked
            time.sleep(_LOCK_POLL)
        except OSError:
            # A transient FS error rather than "already held": on Windows a name
            # that another racer is mid-rmdir on can report a sharing/pending-delete
            # error instead of FileExistsError. Back off briefly and retry rather
            # than letting the read-modify-write crash.
            if time.monotonic() >= deadline:
                _log.warning("lock unavailable (transient FS errors); proceeding "
                             "unlocked on %s", target)
                break
            time.sleep(_LOCK_POLL)
    try:
        yield
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                lock.rmdir()


class State:
    """Handle to one project's on-disk state."""

    def __init__(self, project: str, home: Optional[Path] = None):
        self.project = project
        self.base = Path(home).expanduser() if home else base_dir()
        self.root = self.base / _path_slug(project)

    # -- paths -------------------------------------------------------------- #
    @property
    def meta_path(self) -> Path:
        return self.root / "meta.json"

    @property
    def axes_path(self) -> Path:
        return self.root / "axes.json"

    @property
    def materialized_path(self) -> Path:
        """Durable ledger of pins that entered the graph (candidate_id -> graph ids).
        Written by kg_diverge_materialize; read by the failed-fate sync that folds
        grounding failures back into this project's discard memory (I8). Durable —
        it maps BRIEF state to GRAPH state, and both survive the session."""
        return self.root / "materialized.json"

    def read_materialized(self) -> Dict[str, Any]:
        return self.read_json(self.materialized_path, {}) or {}

    def write_materialized(self, data: Dict[str, Any]) -> None:
        self.write_json(self.materialized_path, data)

    @property
    def session_dir(self) -> Path:
        """I10 ephemeral zone: every geometry artifact (the MAP-Elites archive and
        everything derived from embeddings) lives here and here only, so wiping one
        directory is provably wiping the whole archive."""
        return self.root / "session"

    @property
    def session_path(self) -> Path:
        return self.root / "session.json"

    @property
    def archive_path(self) -> Path:
        return self.session_dir / "archive.json"

    @property
    def candidates_path(self) -> Path:
        return self.session_dir / "candidates.json"

    @property
    def embeddings_path(self) -> Path:
        return self.session_dir / "embeddings.json"

    @property
    def mech_embeddings_path(self) -> Path:
        return self.session_dir / "mech_embeddings.json"

    @property
    def open_nicher_path(self) -> Path:
        return self.session_dir / "open_nicher.json"

    @property
    def tmp_dir(self) -> Path:
        """Per-project scratch dir for the skill's hand-off files (axes.json,
        candidates.json, event.json). Inside the state home so they never clutter
        the user's cwd and can't collide across concurrent sessions."""
        return self.root / "tmp"

    def memory_dir(self, domain: str) -> Path:
        return self.root / "memory" / _path_slug(domain)

    def comparisons_path(self, domain: str) -> Path:
        return self.memory_dir(domain) / "comparisons.jsonl"

    def pins_path(self, domain: str) -> Path:
        return self.memory_dir(domain) / "pins.json"

    def discards_path(self, domain: str) -> Path:
        return self.memory_dir(domain) / "discards.json"

    # -- lifecycle ---------------------------------------------------------- #
    def exists(self) -> bool:
        return self.meta_path.exists()

    def ensure(self) -> "State":
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._sweep_stale_temps()
        return self

    def _sweep_stale_temps(self) -> None:
        """Remove orphaned atomic-write temp files. A crash between ``mkstemp``
        and ``os.replace`` leaves a ``.tmp-*`` file behind; sweep old ones so they
        don't accumulate. Best-effort: races and errors are ignored."""
        cutoff = time.time() - _STALE_TEMP_SECS
        try:
            entries = list(self.root.glob(".tmp-*"))
        except OSError:
            return
        for p in entries:
            with contextlib.suppress(OSError):
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()

    def paths(self) -> Dict[str, str]:
        return {
            "root": str(self.root),
            "meta": str(self.meta_path),
            "axes": str(self.axes_path),
            "session_dir": str(self.session_dir),
            "archive": str(self.archive_path),
            "candidates": str(self.candidates_path),
            "embeddings": str(self.embeddings_path),
            "mech_embeddings": str(self.mech_embeddings_path),
            "open_nicher": str(self.open_nicher_path),
            "tmp": str(self.tmp_dir),
        }

    # -- session lifecycle (I10) --------------------------------------------- #
    # Geometry-coupled meta series: tied to the archive the monitor calibrated
    # against, so they die with it (both on session change and on axes re-init).
    GEOMETRY_META_KEYS = ("cycles", "cos_window", "novelty_window",
                          "erosion_streak", "gap_log")

    def read_session(self) -> Dict[str, Any]:
        return self.read_json(self.session_path, {}) or {}

    def begin_session(self, session_id: str) -> bool:
        """Enforce I10: a NEW session id wipes the ephemeral geometry zone.

        Idempotent for the active session (same id -> nothing wiped), so a
        command may re-run init to resume within one session. Durable state
        (pins, discards, comparisons, meta identity, axes) is never touched;
        the geometry-coupled meta series are dropped alongside the archive
        they calibrated against. Returns True when a wipe happened."""
        sid = str(session_id)
        current = self.read_session()
        if current.get("session_id") == sid:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            return False
        shutil.rmtree(self.session_dir, ignore_errors=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        meta = self.read_meta()
        dropped = False
        for key in self.GEOMETRY_META_KEYS:
            dropped = meta.pop(key, None) is not None or dropped
        if dropped:
            self.write_meta(meta)
        self.write_json(self.session_path,
                        {"session_id": sid, "started_at": time.time()})
        return True

    def reset_geometry(self) -> None:
        """Delete this project's geometric state — the MAP-Elites archive, candidate
        records, embeddings (surface AND the parallel mechanism store), and the frozen
        open-axis nicher — so the project can be re-initialized under a NEW axes
        geometry without mixing stale niche keys with new ones. Preference memory
        (pins/discards/comparisons, namespaced per domain) is deliberately left intact.
        Best-effort: a missing file is not an error."""
        for path in (self.archive_path, self.candidates_path,
                     self.embeddings_path, self.mech_embeddings_path,
                     self.open_nicher_path):
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)

    def project_lock(self, timeout: float = _LOCK_TIMEOUT):
        """Cross-process lock serializing a whole-project read-modify-write cycle.

        ``ingest`` (and an axes-changing ``init``) read the archive/candidates/
        embeddings/meta, mutate them, and write them back; without serialization two
        concurrent cycles on one project would clobber each other (a lost generation).
        Same best-effort ``mkdir`` lock as the pin/discard guard — on timeout it
        proceeds unlocked rather than deadlock. The lock dir sits beside the state
        files as ``<root>/.project.lock``."""
        return _file_lock(self.root / ".project", timeout=timeout)

    # -- generic json helpers ---------------------------------------------- #
    def read_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            # Empty file (e.g. an interrupted write) — treat as absent rather
            # than crash the command; the next write repopulates it.
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            # A non-empty but corrupt state file is surfaced as a clean,
            # operator-facing error instead of a raw traceback.
            raise ConfigError(
                f"state file {path} is corrupt ({exc}); remove it (or restore a "
                f"backup) and retry"
            ) from exc

    def write_json(self, path: Path, obj: Any) -> None:
        _atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))

    # -- typed accessors ---------------------------------------------------- #
    def read_meta(self) -> Dict[str, Any]:
        return self.read_json(self.meta_path, {}) or {}

    def write_meta(self, meta: Dict[str, Any]) -> None:
        self.write_json(self.meta_path, meta)

    def read_axes(self) -> Optional[Dict[str, Any]]:
        return self.read_json(self.axes_path, None)

    def write_axes(self, axes: Dict[str, Any]) -> None:
        self.write_json(self.axes_path, axes)

    def read_archive(self) -> Dict[str, Any]:
        return self.read_json(self.archive_path, {}) or {}

    def write_archive(self, archive: Dict[str, Any]) -> None:
        self.write_json(self.archive_path, archive)

    def read_candidates(self) -> Dict[str, Any]:
        return self.read_json(self.candidates_path, {}) or {}

    def write_candidates(self, candidates: Dict[str, Any]) -> None:
        self.write_json(self.candidates_path, candidates)

    def read_embeddings(self) -> Dict[str, List[float]]:
        return self.read_json(self.embeddings_path, {}) or {}

    def write_embeddings(self, embeddings: Dict[str, List[float]]) -> None:
        self.write_json(self.embeddings_path, embeddings)

    def read_mech_embeddings(self) -> Dict[str, List[float]]:
        return self.read_json(self.mech_embeddings_path, {}) or {}

    def write_mech_embeddings(self, embeddings: Dict[str, List[float]]) -> None:
        self.write_json(self.mech_embeddings_path, embeddings)

    def read_open_nicher(self) -> Optional[Dict[str, Any]]:
        """Persisted open-axis nicher: cold-start accumulation or frozen centroids."""
        return self.read_json(self.open_nicher_path, None)

    def write_open_nicher(self, data: Dict[str, Any]) -> None:
        self.write_json(self.open_nicher_path, data)

    # -- memory (namespaced by domain) ------------------------------------- #
    def append_comparison(self, domain: str, event: Dict[str, Any]) -> None:
        path = self.comparisons_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
        # Single O_APPEND write (not buffered text I/O): under POSIX O_APPEND each
        # write lands atomically at end-of-file, so concurrent appenders can't
        # interleave a short line. read_comparisons also tolerates a torn line.
        data = line.encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    def read_comparisons(self, domain: str) -> List[Dict[str, Any]]:
        path = self.comparisons_path(domain)
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip a truncated/corrupt line (e.g. an interrupted append) so a
                # single bad record can't poison every future read of this domain.
                continue
        return out

    def read_pins(self, domain: str) -> List[str]:
        return self.read_json(self.pins_path(domain), []) or []

    def write_pins(self, domain: str, pins: List[str]) -> None:
        self.write_json(self.pins_path(domain), pins)

    def add_pin(self, domain: str, candidate_id: str) -> List[str]:
        # Lock the read-modify-write so two concurrent invocations can't each read
        # the same list and clobber the other's pin (pins are "never dropped").
        path = self.pins_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _file_lock(path):
            pins = self.read_pins(domain)
            if candidate_id not in pins:
                pins.append(candidate_id)
                self.write_pins(domain, pins)
            # Pins and discards are mutually exclusive (latest action wins): pinning
            # an id the user previously discarded un-discards it.
            self._remove_discard(domain, candidate_id)
            return pins

    def read_discards(self, domain: str) -> List[str]:
        return self.read_json(self.discards_path(domain), []) or []

    def write_discards(self, domain: str, discards: List[str]) -> None:
        self.write_json(self.discards_path(domain), discards)

    def add_discard(self, domain: str, candidate_id: str) -> List[str]:
        # Locked read-modify-write, mirroring add_pin. A discard is the negative of
        # a pin; the two are mutually exclusive (latest action wins), so discarding
        # an id also drops it from pins.
        path = self.discards_path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _file_lock(path):
            discards = self.read_discards(domain)
            if candidate_id not in discards:
                discards.append(candidate_id)
                self.write_discards(domain, discards)
            self._remove_pin(domain, candidate_id)
            return discards

    def _remove_pin(self, domain: str, candidate_id: str) -> None:
        pins = self.read_pins(domain)
        if candidate_id in pins:
            self.write_pins(domain, [p for p in pins if p != candidate_id])

    def _remove_discard(self, domain: str, candidate_id: str) -> None:
        discards = self.read_discards(domain)
        if candidate_id in discards:
            self.write_discards(domain, [d for d in discards if d != candidate_id])
