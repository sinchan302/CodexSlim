"""
File-hash-based cache for slim digests.

Cache store: flat JSON files in <workspace>/.codexslim/cache.json
Cache entry fields:
    path          — relative path from workspace root
    sha256        — SHA-256 of the raw source file at last parse
    slim_digest   — the skeletonized output string
    parsed_at     — ISO-8601 timestamp of last parse
    last_seen_at  — ISO-8601 timestamp of last reconcile scan
    status        — "active" | "pending_eviction"
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock


_CACHE_FILE = ".codexslim/cache.json"
_LOCK_FILE  = ".codexslim/cache.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CacheManager:
    """
    Manages slim digests keyed by file SHA-256 hash.

    Usage:
        cm = CacheManager(workspace_root=Path("."))
        cm.load()

        digest = cm.get(path)          # None on miss
        cm.set(path, sha, digest)      # write entry
        cm.mark_deleted(path)          # flag for grace-period eviction
        cm.evict_expired(grace_hours)  # remove stale entries
        cm.save()
    """

    def __init__(self, workspace_root: Path, grace_hours: float = 24.0) -> None:
        self.root = workspace_root.resolve()
        self.grace_hours = grace_hours
        self._cache_path = self.root / _CACHE_FILE
        self._lock_path  = self.root / _LOCK_FILE
        self._data: dict[str, dict] = {}

    # ── persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load cache from disk. Safe to call even if cache file doesn't exist."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self._cache_path.exists():
            try:
                self._data = json.loads(self._cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        """Persist cache to disk with a file lock."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self._lock_path)):
            self._cache_path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False)
            )

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, path: Path) -> str | None:
        """
        Return a cached slim digest if the file hash still matches.

        Returns None on cache miss or hash mismatch (stale).
        """
        key = self._key(path)
        entry = self._data.get(key)
        if not entry:
            return None
        if entry.get("status") != "active":
            return None
        current_sha = _sha256(path)
        if entry.get("sha256") != current_sha:
            return None  # file changed — caller must re-parse
        # Update last_seen_at without a full save (caller calls save() at end)
        entry["last_seen_at"] = _now_iso()
        return entry["slim_digest"]

    # ── write ─────────────────────────────────────────────────────────────────

    def set(self, path: Path, slim_digest: str) -> None:
        """Store or update a slim digest for a file."""
        key = self._key(path)
        sha = _sha256(path)
        self._data[key] = {
            "path": key,
            "sha256": sha,
            "slim_digest": slim_digest,
            "parsed_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "status": "active",
        }

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def mark_deleted(self, path: Path) -> None:
        """Flag a file as deleted; it will be evicted after the grace period."""
        key = self._key(path)
        if key in self._data:
            self._data[key]["status"] = "pending_eviction"
            self._data[key]["deleted_at"] = _now_iso()

    def evict_expired(self) -> list[str]:
        """
        Remove entries that have been pending eviction longer than grace_hours.

        Returns a list of evicted keys (for logging).
        """
        evicted = []
        grace_seconds = self.grace_hours * 3600
        now = time.time()

        for key, entry in list(self._data.items()):
            if entry.get("status") != "pending_eviction":
                continue
            deleted_at_str = entry.get("deleted_at", entry.get("last_seen_at", ""))
            try:
                deleted_at = datetime.fromisoformat(deleted_at_str).timestamp()
            except ValueError:
                deleted_at = 0.0
            if now - deleted_at >= grace_seconds:
                del self._data[key]
                evicted.append(key)

        return evicted

    def reconcile(self, live_paths: list[Path]) -> dict[str, list[str]]:
        """
        Diff live file tree against cache.

        Marks entries for files that have disappeared as pending_eviction.
        Returns a summary dict with keys 'new', 'changed', 'deleted', 'cached'.
        """
        live_keys = {self._key(p) for p in live_paths}
        cached_keys = set(self._data.keys())

        summary: dict[str, list[str]] = {
            "new": [], "changed": [], "deleted": [], "cached": []
        }

        # Files in cache but not on disk → mark deleted
        for key in cached_keys - live_keys:
            if self._data[key].get("status") == "active":
                self.mark_deleted(self.root / key)
                summary["deleted"].append(key)

        # Files on disk → categorise
        for path in live_paths:
            key = self._key(path)
            if key not in self._data:
                summary["new"].append(key)
            else:
                entry = self._data[key]
                current_sha = _sha256(path)
                if entry.get("sha256") != current_sha:
                    summary["changed"].append(key)
                else:
                    summary["cached"].append(key)

        return summary

    # ── helpers ───────────────────────────────────────────────────────────────

    def _key(self, path: Path) -> str:
        """Normalise path to a relative string key."""
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path)
