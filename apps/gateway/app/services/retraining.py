"""Train local model artifacts from analyst-labeled gateway events."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.ml.artifacts import review_model_artifact
from app.ml.training import LabeledFeatures, train_risk_classifier
from app.schemas.retraining import RetrainingRun
from app.services.training_export import event_to_training_row, training_data_summary
from app.storage import store


def _artifact_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(settings.retraining_artifact_dir) / f"risk_model_{stamp}.joblib"


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
    metrics = train_risk_classifier(rows, output_path)
    review = review_model_artifact(output_path)
    metrics_dict = metrics.__dict__

    return RetrainingRun(
        artifact_path=str(output_path),
        training_summary=summary,
        metrics=metrics_dict,
        review=review.to_dict(),
        next_steps=[
            "Review dataset provenance and artifact metrics.",
            "Set MIRAGE_MODEL_ARTIFACT to this path only for shadow mode.",
            "Keep live routing heuristic until shadow performance is reviewed.",
        ],
    )
