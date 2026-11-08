"""Train local model artifacts from analyst-labeled gateway events."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import uuid

from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.ml.artifact_integrity import sha256_file
from app.ml.artifacts import file_stamp, review_model_artifact
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.schemas.retraining import RetrainingRun
from app.services.training_export import event_to_training_row, training_data_summary
from app.storage import store

logger = logging.getLogger(__name__)
RETAINED_ARTIFACTS = 5


def prune_retraining_artifacts(
    directory: Path, *, keep: int = RETAINED_ARTIFACTS, protected: Path | None
) -> list[Path]:
    """Delete all but the newest ``keep`` retraining artifacts; return what was deleted.

    The ``protected`` artifact (the configured MIRAGE_MODEL_ARTIFACT) is never
    deleted. Deletion errors are logged, never raised.
    """
    protected_path = protected.resolve() if protected else None
    artifacts = sorted(
        directory.glob("risk_model_*.joblib"), key=file_stamp, reverse=True
    )
    deleted: list[Path] = []
    for path in artifacts[keep:]:
        if path.resolve() == protected_path:
            continue
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Could not delete old retraining artifact %s: %s", path, exc)
        else:
            deleted.append(path)
    return deleted


def _artifact_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return Path(settings.retraining_artifact_dir) / f"risk_model_{stamp}_{suffix}.joblib"


async def train_from_labeled_events(limit: int = 10000) -> RetrainingRun:
    """Train and review a local artifact from analyst-labeled events."""
    events = await store.get_labeled_events(limit=limit)
    summary = training_data_summary(events)
    if not summary["ready_for_training"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Training data is not ready",
                "training_summary": summary,
            },
        )

    rows = []
    for event in events:
        row = event_to_training_row(event)
        if row is None:
            continue
        rows.append(
            LabeledFeatures(
                features=row["features"],
                label=int(row["label"]),
            )
        )

    output_path = _artifact_path()

    def train_and_review():
        metrics = train_risk_classifier(rows, output_path)
        result = metrics, review_model_artifact(output_path), sha256_file(output_path)
        configured = settings.ml_model_artifact
        prune_retraining_artifacts(
            output_path.parent, protected=Path(configured) if configured else None
        )
        return result

    # Training takes seconds; keep the event loop serving traffic meanwhile.
    metrics, review, artifact_sha256 = await run_in_threadpool(train_and_review)
    metrics_dict = metrics.__dict__

    return RetrainingRun(
        artifact_path=str(output_path),
        artifact_sha256=artifact_sha256,
        training_summary=summary,
        metrics=metrics_dict,
        review=review.to_dict(),
        next_steps=[
            "Review dataset provenance and artifact metrics.",
            "Set MIRAGE_MODEL_ARTIFACT to this path only for shadow mode.",
            "Keep live routing heuristic until shadow performance is reviewed.",
            "Set MIRAGE_MODEL_ARTIFACT_SHA256 to artifact_sha256 to pin the file.",
        ],
    )
