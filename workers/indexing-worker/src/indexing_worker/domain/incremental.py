from __future__ import annotations

from dataclasses import dataclass

from indexing_worker.domain.models import ManifestEntry, SnapshotManifest


@dataclass(frozen=True, slots=True)
class ManifestDiff:
    added: tuple[ManifestEntry, ...]
    changed: tuple[ManifestEntry, ...]
    removed: tuple[ManifestEntry, ...]

    @property
    def impacted_paths(self) -> frozenset[str]:
        paths = {e.path for e in self.added} | {e.path for e in self.changed} | {
            e.path for e in self.removed
        }
        return frozenset(paths)


class IncrementalDiffEngine:
    """Manifest path+hash diff for incremental indexing (LLD §7.5)."""

    def diff(
        self,
        parent: SnapshotManifest | None,
        current: SnapshotManifest,
    ) -> ManifestDiff:
        if parent is None:
            return ManifestDiff(added=current.entries, changed=(), removed=())

        parent_map = parent.by_path()
        current_map = current.by_path()

        added: list[ManifestEntry] = []
        changed: list[ManifestEntry] = []
        removed: list[ManifestEntry] = []

        for path, entry in current_map.items():
            prior = parent_map.get(path)
            if prior is None:
                added.append(entry)
            elif prior.content_hash != entry.content_hash:
                changed.append(entry)

        for path, entry in parent_map.items():
            if path not in current_map:
                removed.append(entry)

        return ManifestDiff(
            added=tuple(added),
            changed=tuple(changed),
            removed=tuple(removed),
        )
