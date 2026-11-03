"""Typed, provenance-preserving research artifact records."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alem.errors import AlemError
from alem.projects import slugify
from alem.workspace import Workspace

ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
EVIDENCE_STATUSES = {
    "verified_evidence",
    "reported_finding",
    "interpretation",
    "hypothesis",
    "unverified",
}


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    schema_version: int
    id: str
    artifact_type: str
    created_at: str
    creator: str
    source: str
    evidence_status: str
    path: str
    digest_sha256: str
    inputs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _project_root(workspace: Workspace, project: str) -> Path:
    root = workspace.path("projects", slugify(project))
    if not (root / "PROJECT.md").is_file():
        raise AlemError(f"unknown research project: {project}")
    return root


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def register_artifact(
    workspace: Workspace,
    project: str,
    path: str | Path,
    *,
    artifact_type: str,
    creator: str,
    source: str,
    evidence_status: str = "unverified",
    inputs: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
) -> ArtifactRecord:
    if not ARTIFACT_TYPE.fullmatch(artifact_type):
        raise AlemError("artifact type must be a lowercase dotted or snake_case identifier")
    if evidence_status not in EVIDENCE_STATUSES:
        raise AlemError(
            "evidence status must be one of: " + ", ".join(sorted(EVIDENCE_STATUSES))
        )
    if not creator.strip() or not source.strip():
        raise AlemError("artifact creator and source are required")
    project_root = _project_root(workspace, project)
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else project_root / candidate
    candidate = workspace.assert_local(candidate)
    try:
        relative = candidate.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise AlemError("artifact must be inside the selected project") from exc
    if not candidate.is_file():
        raise AlemError(f"artifact file does not exist: {relative.as_posix()}")
    digest = _digest(candidate)
    identity = hashlib.sha256(
        f"{artifact_type}\0{relative.as_posix()}\0{digest}\0{source}".encode()
    ).hexdigest()[:20]
    artifact_id = f"art-{identity}"
    records_root = project_root / "provenance" / "artifacts"
    records_root.mkdir(parents=True, exist_ok=True)
    for input_id in inputs:
        if not (records_root / f"{input_id}.json").is_file():
            raise AlemError(f"unknown input artifact: {input_id}")
    record = ArtifactRecord(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        id=artifact_id,
        artifact_type=artifact_type,
        created_at=datetime.now(UTC).isoformat(),
        creator=creator.strip(),
        source=source.strip(),
        evidence_status=evidence_status,
        path=relative.as_posix(),
        digest_sha256=digest,
        inputs=inputs,
        metadata=dict(metadata or {}),
    )
    target = records_root / f"{artifact_id}.json"
    target.write_text(
        json.dumps(record.to_mapping(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record


def load_artifact(workspace: Workspace, project: str, artifact_id: str) -> ArtifactRecord:
    project_root = _project_root(workspace, project)
    path = project_root / "provenance" / "artifacts" / f"{artifact_id}.json"
    if not path.is_file():
        raise AlemError(f"unknown artifact: {artifact_id}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlemError(f"cannot read artifact record {artifact_id}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise AlemError(f"invalid artifact record: {artifact_id}")
    raw["inputs"] = tuple(raw.get("inputs", ()))
    return ArtifactRecord(**raw)


def list_artifacts(workspace: Workspace, project: str) -> list[ArtifactRecord]:
    root = _project_root(workspace, project) / "provenance" / "artifacts"
    if not root.exists():
        return []
    return [
        load_artifact(workspace, project, path.stem)
        for path in sorted(root.glob("art-*.json"))
    ]


def verify_artifact(workspace: Workspace, project: str, artifact_id: str) -> dict[str, Any]:
    project_root = _project_root(workspace, project)
    record = load_artifact(workspace, project, artifact_id)
    path = project_root / record.path
    present = path.is_file()
    actual = _digest(path) if present else None
    return {
        "id": artifact_id,
        "present": present,
        "expected_digest": record.digest_sha256,
        "actual_digest": actual,
        "valid": present and actual == record.digest_sha256,
    }
