"""Train and persist the first MIRAGE request-risk classifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from app.services.feature_extraction import FEATURE_NAMES, FeatureVector


@dataclass(frozen=True)
class LabeledFeatures:
    features: FeatureVector
    label: int


@dataclass(frozen=True)
class TrainingMetrics:
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    training_rows: int
    test_rows: int


def _matrix(rows: list[LabeledFeatures]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(
        [[row.features.get(name, 0.0) for name in FEATURE_NAMES] for row in rows],
        dtype=float,
    )
    y = np.asarray([row.label for row in rows], dtype=int)
    return x, y


def train_risk_classifier(
    rows: Iterable[LabeledFeatures],
    output_path: Path,
    *,
    random_state: int = 42,
) -> TrainingMetrics:
    """Train a deterministic binary classifier and save a versioned artifact."""
    records = list(rows)
    if len(records) < 20:
        raise ValueError("At least 20 labeled rows are required")
    if {row.label for row in records} != {0, 1}:
        raise ValueError("Training data must contain both normal and suspicious labels")

    x, y = _matrix(records)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.25,
        stratify=y,
        random_state=random_state,
    )
    model = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    tn, fp, _, _ = confusion_matrix(y_test, predictions, labels=[0, 1]).ravel()
    metrics = TrainingMetrics(
        precision=float(precision_score(y_test, predictions, zero_division=0)),
        recall=float(recall_score(y_test, predictions, zero_division=0)),
        f1_score=float(f1_score(y_test, predictions, zero_division=0)),
        false_positive_rate=float(fp / (fp + tn)) if fp + tn else 0.0,
        training_rows=len(y_train),
        test_rows=len(y_test),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "metrics": asdict(metrics),
            "artifact_version": 1,
        },
        output_path,
    )
    return metrics
