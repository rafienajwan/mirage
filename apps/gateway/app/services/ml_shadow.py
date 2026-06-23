"""Optional ML scoring that observes traffic without changing routing."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.ml.inference import RiskClassifier
from app.schemas.decision import Decision
from app.schemas.ml import MLShadowScore
from app.services.feature_extraction import FeatureVector

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_classifier() -> RiskClassifier | None:
    artifact = settings.ml_model_artifact
    if not artifact:
        return None

    artifact_path = Path(artifact)
    if not artifact_path.exists():
        logger.warning("ML shadow artifact does not exist: %s", artifact_path)
        return None

    try:
        return RiskClassifier(artifact_path)
    except (KeyError, ValueError, OSError) as exc:
        logger.warning("ML shadow artifact could not be loaded: %s", exc)
        return None


def _decision_from_probability(probability: float) -> Decision:
    if probability >= settings.ml_shadow_redirect_threshold:
        return Decision.REDIRECT_TO_DECOY
    if probability >= settings.ml_shadow_monitor_threshold:
        return Decision.MONITOR
    return Decision.ALLOW


def score_ml_shadow(
    features: FeatureVector, *, heuristic_decision: Decision
) -> MLShadowScore | None:
    """Return an optional model score without affecting the live decision."""
    classifier = _load_classifier()
    if classifier is None:
        return None

    probability = classifier.suspicious_probability(features)
    shadow_decision = _decision_from_probability(probability)
    return MLShadowScore(
        artifact=Path(settings.ml_model_artifact or "").name,
        probability=round(probability, 6),
        score=round(probability * 100, 2),
        prediction="suspicious" if probability >= 0.5 else "normal",
        shadow_decision=shadow_decision.value,
        agrees_with_decision=shadow_decision == heuristic_decision,
    )
