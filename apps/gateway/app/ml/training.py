"""Train and persist the first MIRAGE request-risk classifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.ml.artifacts import classification_metrics
from app.ml.datasets import PreparedTrainingRow, stratified_split
from app.services.feature_extraction import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_NAMES,
    FeatureVector,
)


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


def _matrix(
    rows: list[LabeledFeatures] | list[PreparedTrainingRow],
) -> tuple[np.ndarray, np.ndarray]:
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
    dataset_lineage: dict[str, str] | None = None,
    test_rows: Iterable[LabeledFeatures] | None = None,
) -> TrainingMetrics:
    """Train a deterministic binary classifier and save a versioned artifact.

    With ``test_rows`` (a prepared held-out split) the model fits on every
    training row and is scored on those rows; otherwise about 25% is held out
    here, keeping rows with identical feature vectors on the same side.
    """
    records = list(rows)
    if len(records) < 20:
        raise ValueError("At least 20 labeled rows are required")
    if {row.label for row in records} != {0, 1}:
        raise ValueError("Training data must contain both normal and suspicious labels")

    if test_rows is None:
        split = stratified_split(
            [
                PreparedTrainingRow(
                    features={name: row.features.get(name, 0.0) for name in FEATURE_NAMES},
                    label=row.label,
                )
                for row in records
            ],
            train_ratio=0.75,
            random_seed=random_state,
        )
        x_train, y_train = _matrix(split.train)
        x_test, y_test = _matrix(split.test)
    else:
        held_out = list(test_rows)
        if {row.label for row in held_out} != {0, 1}:
            raise ValueError("Test data must contain both normal and suspicious labels")
        x_train, y_train = _matrix(records)
        x_test, y_test = _matrix(held_out)
    model = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    metrics = TrainingMetrics(
        **classification_metrics(y_test, model.predict(x_test)),
        training_rows=len(y_train),
        test_rows=len(y_test),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "feature_names": FEATURE_NAMES,
            "metrics": asdict(metrics),
            "artifact_version": 2 if dataset_lineage else 1,
            "dataset_lineage": dataset_lineage,
        },
        output_path,
    )
    return metrics
