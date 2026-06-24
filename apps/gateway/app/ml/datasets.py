"""Dataset validation and preparation helpers for MIRAGE model training."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from app.services.feature_extraction import FEATURE_NAMES, FeatureVector


DatasetSource = Literal["mirage-jsonl", "cicids-csv"]


@dataclass(frozen=True)
class PreparedTrainingRow:
    """Validated binary training row with a stable MIRAGE feature vector."""

    features: FeatureVector
    label: int
    source: str | None = None
    record_id: str | None = None


@dataclass(frozen=True)
class DatasetManifest:
    """Provenance and split metadata for a prepared training dataset."""

    dataset_name: str
    dataset_version: str
    source_kind: DatasetSource
    generated_at: str
    total_rows: int
    train_rows: int
    test_rows: int
    label_counts: dict[str, int]
    train_label_counts: dict[str, int]
    test_label_counts: dict[str, int]
    train_ratio: float
    random_seed: int
    feature_names: list[str]
    files: dict[str, str]


class DatasetValidationError(ValueError):
    """Raised when source data cannot be converted into trainable rows."""


def normalize_features(features: object, *, line_number: int | None = None) -> FeatureVector:
    """Return a numeric feature vector with exactly MIRAGE's known feature names."""
    if not isinstance(features, dict):
        location = f" on line {line_number}" if line_number else ""
        raise DatasetValidationError(f"features must be an object{location}")

    normalized: FeatureVector = {}
    for name in FEATURE_NAMES:
        value = features.get(name, 0.0)
        try:
            normalized[name] = float(value)
        except (TypeError, ValueError) as exc:
            location = f" on line {line_number}" if line_number else ""
            raise DatasetValidationError(
                f"feature {name!r} must be numeric{location}"
            ) from exc
    return normalized


def normalize_label(label: object, *, line_number: int | None = None) -> int:
    """Normalize a binary label into 0 normal or 1 suspicious."""
    try:
        normalized = int(label)
    except (TypeError, ValueError) as exc:
        location = f" on line {line_number}" if line_number else ""
        raise DatasetValidationError(f"label must be 0 or 1{location}") from exc
    if normalized not in {0, 1}:
        location = f" on line {line_number}" if line_number else ""
        raise DatasetValidationError(f"label must be 0 or 1{location}")
    return normalized


def load_mirage_jsonl(path: Path) -> list[PreparedTrainingRow]:
    """Load MIRAGE JSONL rows produced by the analyst-labeled export endpoint."""
    rows: list[PreparedTrainingRow] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetValidationError(
                    f"invalid JSON on line {line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise DatasetValidationError(
                    f"training row must be an object on line {line_number}"
                )
            rows.append(
                PreparedTrainingRow(
                    features=normalize_features(
                        record.get("features"),
                        line_number=line_number,
                    ),
                    label=normalize_label(
                        record.get("label"),
                        line_number=line_number,
                    ),
                    source="mirage-jsonl",
                    record_id=str(record.get("event_id") or line_number),
                )
            )
    return rows


def _first_present(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return None


def _float_field(row: dict[str, str], *names: str) -> float:
    value = _first_present(row, *names)
    if value is None:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _label_from_cicids(value: str | None) -> int:
    if value is None:
        raise DatasetValidationError("CICIDS row is missing Label")
    return 0 if value.strip().upper() == "BENIGN" else 1


def load_cicids_csv(path: Path) -> list[PreparedTrainingRow]:
    """Load a CICIDS-style CSV into the MIRAGE feature schema.

    Columns that do not exist in a given CICIDS export are filled with zero so
    the resulting rows remain compatible with the current model feature order.
    """
    rows: list[PreparedTrainingRow] = []
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        for line_number, record in enumerate(reader, start=2):
            label = _label_from_cicids(_first_present(record, "Label", "label"))
            features: FeatureVector = {
                "request_count_log": 0.0,
                "path_length": 0.0,
                "path_depth": 0.0,
                "sensitive_path": 0.0,
                "suspicious_user_agent": 0.0,
                "high_risk_indicator_count": 0.0,
                "medium_risk_indicator_count": 0.0,
                "method_get": 0.0,
                "method_post": 0.0,
                "method_write": 0.0,
                "flow_duration_ms": _float_field(
                    record,
                    "Flow Duration",
                    "Flow Duration_ms",
                    "flow_duration_ms",
                ),
                "flow_packets_per_second": _float_field(
                    record,
                    "Flow Packets/s",
                    "Flow Packets Per Second",
                    "flow_packets_per_second",
                ),
                "packet_length_mean": _float_field(
                    record,
                    "Packet Length Mean",
                    "packet_length_mean",
                ),
                "syn_flag_count": _float_field(
                    record,
                    "SYN Flag Count",
                    "syn_flag_count",
                ),
                "destination_port": _float_field(
                    record,
                    "Destination Port",
                    "Dst Port",
                    "destination_port",
                ),
                "average_packet_size": _float_field(
                    record,
                    "Average Packet Size",
                    "Avg Packet Size",
                    "average_packet_size",
                ),
            }
            rows.append(
                PreparedTrainingRow(
                    features=normalize_features(features, line_number=line_number),
                    label=label,
                    source="cicids-csv",
                    record_id=str(line_number),
                )
            )
    return rows


def load_dataset(path: Path, source_kind: DatasetSource) -> list[PreparedTrainingRow]:
    """Load source data using the selected adapter."""
    if source_kind == "mirage-jsonl":
        return load_mirage_jsonl(path)
    if source_kind == "cicids-csv":
        return load_cicids_csv(path)
    raise DatasetValidationError(f"Unsupported dataset source kind: {source_kind}")


def validate_training_rows(rows: Iterable[PreparedTrainingRow]) -> list[PreparedTrainingRow]:
    """Validate minimum size and class balance required by the trainer."""
    validated = list(rows)
    if len(validated) < 20:
        raise DatasetValidationError("At least 20 labeled rows are required")

    counts = Counter(row.label for row in validated)
    if set(counts) != {0, 1}:
        raise DatasetValidationError(
            "Training data must contain both normal and suspicious labels"
        )
    if counts[0] < 2 or counts[1] < 2:
        raise DatasetValidationError(
            "Each binary class must contain at least two rows"
        )
    return validated


def stratified_split(
    rows: Iterable[PreparedTrainingRow],
    *,
    train_ratio: float = 0.75,
    random_seed: int = 42,
) -> tuple[list[PreparedTrainingRow], list[PreparedTrainingRow]]:
    """Create a deterministic stratified train/test split."""
    if not 0 < train_ratio < 1:
        raise DatasetValidationError("train_ratio must be between 0 and 1")

    grouped: dict[int, list[PreparedTrainingRow]] = {0: [], 1: []}
    for row in validate_training_rows(rows):
        grouped[row.label].append(row)

    train: list[PreparedTrainingRow] = []
    test: list[PreparedTrainingRow] = []
    rng = random.Random(random_seed)

    for label_rows in grouped.values():
        shuffled = list(label_rows)
        rng.shuffle(shuffled)
        split_at = round(len(shuffled) * train_ratio)
        split_at = min(max(split_at, 1), len(shuffled) - 1)
        train.extend(shuffled[:split_at])
        test.extend(shuffled[split_at:])

    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def _row_to_json(row: PreparedTrainingRow) -> dict:
    data = {
        "label": row.label,
        "features": {name: row.features.get(name, 0.0) for name in FEATURE_NAMES},
    }
    if row.source:
        data["source"] = row.source
    if row.record_id:
        data["record_id"] = row.record_id
    return data


def write_jsonl(path: Path, rows: Iterable[PreparedTrainingRow]) -> None:
    """Write prepared rows as JSON Lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(_row_to_json(row), sort_keys=True))
            target.write("\n")


def prepare_dataset(
    input_path: Path,
    output_dir: Path,
    *,
    source_kind: DatasetSource,
    dataset_name: str,
    dataset_version: str,
    train_ratio: float = 0.75,
    random_seed: int = 42,
) -> DatasetManifest:
    """Validate, split, and write a versioned training dataset."""
    rows = load_dataset(input_path, source_kind)
    train_rows, test_rows = stratified_split(
        rows,
        train_ratio=train_ratio,
        random_seed=random_seed,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    test_path = output_dir / "test.jsonl"
    manifest_path = output_dir / "manifest.json"

    write_jsonl(train_path, train_rows)
    write_jsonl(test_path, test_rows)

    label_counts = Counter(row.label for row in rows)
    train_label_counts = Counter(row.label for row in train_rows)
    test_label_counts = Counter(row.label for row in test_rows)
    manifest = DatasetManifest(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        source_kind=source_kind,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_rows=len(rows),
        train_rows=len(train_rows),
        test_rows=len(test_rows),
        label_counts={str(label): label_counts[label] for label in (0, 1)},
        train_label_counts={str(label): train_label_counts[label] for label in (0, 1)},
        test_label_counts={str(label): test_label_counts[label] for label in (0, 1)},
        train_ratio=train_ratio,
        random_seed=random_seed,
        feature_names=list(FEATURE_NAMES),
        files={
            "train": train_path.name,
            "test": test_path.name,
            "manifest": manifest_path.name,
        },
    )

    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest
