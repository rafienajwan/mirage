"""Read-only status reporting for optional ML shadow scoring."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.ml.artifact_integrity import UNPINNED_BLOCKER, pinned_digest
from app.ml.artifacts import cached_artifact_review


def get_ml_shadow_status() -> dict:
    """Return sanitized ML shadow configuration and artifact readiness."""
    artifact = settings.ml_model_artifact
    base_status = {
        "artifact": None,
        "shadow_ready": False,
        "monitor_threshold": settings.ml_shadow_monitor_threshold,
        "redirect_threshold": settings.ml_shadow_redirect_threshold,
        "metrics": {},
        "blockers": [],
        "warnings": [],
    }

    if not artifact:
        return {
            **base_status,
            "mode": "disabled",
            "blockers": ["MIRAGE_MODEL_ARTIFACT is not configured"],
        }

    artifact_path = Path(artifact)
    expected_sha256, may_load = pinned_digest(settings)
    if not may_load:
        return {
            **base_status,
            "mode": "invalid",
            "artifact": artifact_path.name,
            "blockers": [UNPINNED_BLOCKER],
        }
    review = cached_artifact_review(artifact_path, expected_sha256=expected_sha256)
    if "Artifact file does not exist" in review.blockers:
        mode = "missing"
    elif review.shadow_ready:
        mode = "shadow_ready"
    else:
        mode = "invalid"

    return {
        **base_status,
        "mode": mode,
        "artifact": artifact_path.name,
        "shadow_ready": review.shadow_ready,
        "metrics": review.metrics,
        "blockers": review.blockers,
        "warnings": review.warnings,
    }
