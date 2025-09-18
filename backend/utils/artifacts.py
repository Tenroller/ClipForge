"""Artifact persistence utilities.

Provides a very lightweight manifest based persistence layer for
workflow step artifacts so that resumed jobs can optionally skip
already completed (and often expensive) steps.

Design goals:
1. Zero external dependencies (JSON + filesystem only)
2. Explicit – each step writes its own manifest file
3. Safe – never overwrite an existing manifest unless force=True
4. Transparent – manifest schema is simple and documented below

Directory layout (under the global output directory):

  <OUTPUT>/<job_id>/artifacts/
      manifest.json                # High-level job artifact index
      <step_name>/
          <artifact_key>.json      # JSON serializable artifact
          <artifact_key>.meta.json # Optional metadata (e.g. timing)

The top-level manifest.json keeps a quick index of which steps
have persisted artifacts and simple metadata (timestamp, size).

This module intentionally keeps I/O small and side‑effect free;
callers are responsible for ensuring thread safety at a higher
level (job execution is already serialized per job in the queue).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

from .paths import get_output_path


@dataclass
class ArtifactInfo:
    step: str
    key: str
    created_at: str
    size_bytes: int
    meta: Optional[Dict[str, Any]] = None


def _job_artifacts_root(job_id: str) -> Path:
    return get_output_path() / job_id / "artifacts"


def _step_dir(job_id: str, step: str) -> Path:
    return _job_artifacts_root(job_id) / step


def _manifest_path(job_id: str) -> Path:
    return _job_artifacts_root(job_id) / "manifest.json"


def load_manifest(job_id: str) -> Dict[str, Any]:
    """Load (or create empty) job artifact manifest."""
    mp = _manifest_path(job_id)
    if mp.exists():
        try:
            return json.loads(mp.read_text("utf-8"))
        except Exception:
            # Corrupt manifest – rename it and return empty
            mp.rename(mp.with_suffix(".corrupt.json"))
    return {"job_id": job_id, "artifacts": {}}


def save_manifest(job_id: str, manifest: Dict[str, Any]) -> None:
    mp = _manifest_path(job_id)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")


def persist_artifact(job_id: str, step: str, key: str, payload: Any, *, meta: Optional[Dict[str, Any]] = None, force: bool = False) -> ArtifactInfo:
    """Persist a JSON-serializable artifact for a step.

    Returns ArtifactInfo describing the persisted artifact.
    """
    step_path = _step_dir(job_id, step)
    step_path.mkdir(parents=True, exist_ok=True)
    artifact_file = step_path / f"{key}.json"
    if artifact_file.exists() and not force:
        # Return existing info without overwriting
        data = json.loads(artifact_file.read_text("utf-8"))
        size = artifact_file.stat().st_size
        return ArtifactInfo(step=step, key=key, created_at=datetime.fromtimestamp(artifact_file.stat().st_mtime, timezone.utc).isoformat(), size_bytes=size, meta=meta)

    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    artifact_file.write_text(serialized, "utf-8")
    size = len(serialized.encode("utf-8"))
    info = ArtifactInfo(step=step, key=key, created_at=datetime.now(timezone.utc).isoformat(), size_bytes=size, meta=meta)

    # Update manifest index
    manifest = load_manifest(job_id)
    manifest_artifacts = manifest.setdefault("artifacts", {})
    step_index = manifest_artifacts.setdefault(step, {})
    step_index[key] = asdict(info)
    save_manifest(job_id, manifest)
    return info


def load_artifact(job_id: str, step: str, key: str) -> Optional[Any]:
    """Load an artifact if present."""
    artifact_file = _step_dir(job_id, step) / f"{key}.json"
    if not artifact_file.exists():
        return None
    try:
        return json.loads(artifact_file.read_text("utf-8"))
    except Exception:
        return None


def has_artifact(job_id: str, step: str, key: str) -> bool:
    return (_step_dir(job_id, step) / f"{key}.json").exists()


def list_step_artifacts(job_id: str, step: str) -> List[str]:
    d = _step_dir(job_id, step)
    if not d.exists():
        return []
    return [p.stem for p in d.glob("*.json")]


def summarize_artifacts(job_id: str) -> Dict[str, Any]:
    manifest = load_manifest(job_id)
    return {
        "job_id": job_id,
        "steps": list((manifest.get("artifacts") or {}).keys()),
        "counts": {step: len(entries) for step, entries in (manifest.get("artifacts") or {}).items()},
    }
