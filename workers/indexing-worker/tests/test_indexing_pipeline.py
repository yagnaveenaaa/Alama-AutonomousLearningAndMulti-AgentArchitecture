from __future__ import annotations

from uuid import uuid4

import pytest

from indexing_worker.container import build_container
from indexing_worker.domain.incremental import IncrementalDiffEngine
from indexing_worker.domain.models import (
    IndexGenerationState,
    IndexJob,
    ManifestEntry,
    SnapshotManifest,
    SymbolKind,
)
from indexing_worker.main import process_one

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


SAMPLE_PY = '''\
"""Demo module."""

class Greeter:
    def hello(self, name: str) -> str:
        return f"hi {name}"

def add(a: int, b: int) -> int:
    return a + b
'''


@pytest.mark.asyncio
async def test_pipeline_indexes_python_snapshot() -> None:
    container = build_container()
    tenant_id = uuid4()
    repository_id = uuid4()
    snapshot_id = uuid4()
    manifest_ref = f"snapshots/{repository_id}/{COMMIT_A}.json"

    container.snapshot_source.put_snapshot(
        manifest_ref=manifest_ref,
        repository_id=repository_id,
        commit_sha=COMMIT_A,
        parent_commit_sha=None,
        files={
            "src/demo.py": SAMPLE_PY,
            "README.md": "# Demo\n\n## Usage\n\nCall add().\n",
            "requirements.txt": "fastapi==0.115.0\n",
        },
    )

    await container.queue.enqueue(
        IndexJob(
            tenant_id=tenant_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            commit_sha=COMMIT_A,
            manifest_ref=manifest_ref,
        )
    )

    assert await process_one(container) is True

    active = await container.meta.get_active(repository_id)
    assert active is not None
    assert active.state == IndexGenerationState.ACTIVE
    assert active.embedding_model == container.embedder.model_name
    assert active.stats.symbol_count >= 3
    assert active.stats.chunk_count >= 1
    assert active.stats.embedded_count == active.stats.chunk_count

    symbols = await container.meta.list_symbols(active.id)
    kinds = {s.kind for s in symbols}
    assert SymbolKind.CLASS in kinds
    assert SymbolKind.FUNCTION in kinds

    status, gen_id, err = container.store.snapshot_states[snapshot_id]
    assert status == "ready"
    assert gen_id == active.id
    assert err is None

    assert active.vector_namespace in container.vectors.namespaces
    assert len(container.vectors.namespaces[active.vector_namespace]) == active.stats.embedded_count
    assert active.lexical_index_name in container.lexical.indexes


@pytest.mark.asyncio
async def test_incremental_diff_detects_changed_and_removed() -> None:
    repo = uuid4()
    parent = SnapshotManifest(
        repository_id=repo,
        commit_sha=COMMIT_A,
        parent_commit_sha=None,
        entries=(
            ManifestEntry(path="a.py", content_hash="111", size_bytes=10, language="python"),
            ManifestEntry(path="b.py", content_hash="222", size_bytes=10, language="python"),
        ),
    )
    current = SnapshotManifest(
        repository_id=repo,
        commit_sha=COMMIT_B,
        parent_commit_sha=COMMIT_A,
        entries=(
            ManifestEntry(path="a.py", content_hash="111", size_bytes=10, language="python"),
            ManifestEntry(path="c.py", content_hash="333", size_bytes=10, language="python"),
        ),
    )
    diff = IncrementalDiffEngine().diff(parent, current)
    assert [e.path for e in diff.added] == ["c.py"]
    assert [e.path for e in diff.removed] == ["b.py"]
    assert diff.changed == ()


@pytest.mark.asyncio
async def test_second_generation_retires_previous() -> None:
    container = build_container()
    tenant_id = uuid4()
    repository_id = uuid4()
    snap1 = uuid4()
    snap2 = uuid4()
    ref_a = f"snapshots/{repository_id}/{COMMIT_A}.json"
    ref_b = f"snapshots/{repository_id}/{COMMIT_B}.json"

    container.snapshot_source.put_snapshot(
        manifest_ref=ref_a,
        repository_id=repository_id,
        commit_sha=COMMIT_A,
        parent_commit_sha=None,
        files={"src/demo.py": "def one():\n    return 1\n"},
    )
    container.snapshot_source.put_snapshot(
        manifest_ref=ref_b,
        repository_id=repository_id,
        commit_sha=COMMIT_B,
        parent_commit_sha=COMMIT_A,
        files={"src/demo.py": "def two():\n    return 2\n"},
    )

    await container.queue.enqueue(
        IndexJob(
            tenant_id=tenant_id,
            repository_id=repository_id,
            snapshot_id=snap1,
            commit_sha=COMMIT_A,
            manifest_ref=ref_a,
        )
    )
    await process_one(container)
    first = await container.meta.get_active(repository_id)
    assert first is not None

    await container.queue.enqueue(
        IndexJob(
            tenant_id=tenant_id,
            repository_id=repository_id,
            snapshot_id=snap2,
            commit_sha=COMMIT_B,
            parent_commit_sha=COMMIT_A,
            manifest_ref=ref_b,
        )
    )
    await process_one(container)
    second = await container.meta.get_active(repository_id)
    assert second is not None
    assert second.id != first.id
    assert second.state == IndexGenerationState.ACTIVE

    retired = await container.meta.get_generation(first.id)
    assert retired is not None
    assert retired.state == IndexGenerationState.RETIRED
