"""Dataset validation and preparation helpers for MIRAGE model training."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import shutil
from typing import Iterable, Literal

from app.ml.api_log_review import (
    API_LOG_LABEL_FIELDS,
    _api_log_request,
    _first_object_value,
    _label_from_api_log,
    load_reviewed_api_log_rows,
    validate_api_log_source_review,
)
from app.ml.artifact_integrity import sha256_file
from app.ml.csic_http import (
    CSIC_DISTRIBUTION_URL,
    CSIC_SOURCE_URL,
    LoadedCSICHTTP,
    load_csic_http_directory,
)
from app.ml.errors import DatasetValidationError
from app.schemas.request import InspectRequest
from app.services.feature_extraction import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_NAMES,
    FeatureVector,
    extract_features,
)
from app.services.payload_signals import (
    build_payload_excerpt,
    detect_payload_indicators,
)

DatasetSource = Literal[
    "mirage-jsonl",
    "api-log-jsonl",
    "reviewed-api-log-jsonl",
    "csic-http-dir",
]


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
    feature_contract_version: int
    feature_names: list[str]
    files: dict[str, str]
    file_sha256: dict[str, str] = field(default_factory=dict)
    source_url: str | None = None
    distribution_url: str | None = None
    input_sha256: dict[str, str] = field(default_factory=dict)
    duplicate_rows_removed: int = 0
    rejected_rows: int = 0


def normalize_features(features: object, *, line_number: int | None = None) -> FeatureVector:
    """Return the numeric feature vector in MIRAGE's feature order.

    The keys must be exactly FEATURE_NAMES: a missing feature silently set to 0
    or an unknown one silently dropped would train on a different contract.
    """
    location = f" on line {line_number}" if line_number else ""
    if not isinstance(features, dict):
        raise DatasetValidationError(f"features must be an object{location}")
    if set(features) != set(FEATURE_NAMES):
        missing = sorted(set(FEATURE_NAMES) - set(features))
        unknown = sorted(set(features) - set(FEATURE_NAMES))
        raise DatasetValidationError(
            f"feature names do not match the feature contract{location} "
            f"(missing: {missing}, unknown: {unknown})"
        )

    normalized: FeatureVector = {}
    for name in FEATURE_NAMES:
        value = features[name]
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise DatasetValidationError(
                f"feature {name!r} must be numeric{location}"
            ) from exc
        normalized[name] = numeric_value if math.isfinite(numeric_value) else 0.0
    return normalized


def normalize_label(label: object, *, line_number: int | None = None) -> int:
    """Normalize a binary label into 0 normal or 1 suspicious.

    Only 0, 1, "0" and "1" are accepted: int() would turn 0.5 into 0 and
    True into 1, silently relabelling rows.
    """
    if type(label) is int and label in (0, 1):
        return label
    if label in ("0", "1"):
        return int(label)
    location = f" on line {line_number}" if line_number else ""
    raise DatasetValidationError(f"label must be 0 or 1{location}")


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


def load_api_log_jsonl(path: Path) -> list[PreparedTrainingRow]:
    """Load labeled custom API logs and extract MIRAGE production features."""
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
                    f"API log row must be an object on line {line_number}"
                )

            label = _label_from_api_log(
                _first_object_value(record, *API_LOG_LABEL_FIELDS),
                line_number=line_number,
            )
            request = _api_log_request(record, line_number=line_number)
            rows.append(
                PreparedTrainingRow(
                    features=extract_features(request),
                    label=label,
                    source="api-log-jsonl",
                    record_id=str(
                        _first_object_value(record, "event_id", "request_id", "id")
                        or line_number
                    ),
                )
            )
    return rows


def load_reviewed_api_log_jsonl(path: Path) -> list[PreparedTrainingRow]:
    """Load deduplicated reviewed logs with privacy-safe record identifiers."""
    return [
        PreparedTrainingRow(
            features=row.features,
            label=row.label,
            source="reviewed-api-log-jsonl",
            record_id=row.record_id,
        )
        for row in load_reviewed_api_log_rows(path)
    ]


def _csic_http_rows(loaded: LoadedCSICHTTP) -> list[PreparedTrainingRow]:
    rows: list[PreparedTrainingRow] = []
    for record in loaded.records:
        indicators = detect_payload_indicators(
            record.path,
            record.query,
            record.body,
        )
        request = InspectRequest(
            ip_address="127.0.0.1",
            method=record.method,
            path=record.path[:2048],
            user_agent=record.user_agent[:512],
            payload_indicators=indicators,
            payload_excerpt=build_payload_excerpt(
                record.query,
                # Same decoding as the proxy, so train and serve features match.
                record.body.decode("utf-8", errors="ignore"),
            ),
        )
        rows.append(
            PreparedTrainingRow(
                features=extract_features(request),
                label=record.label,
                source="csic-http-dir",
                record_id=record.record_id,
            )
        )
    return rows


def load_csic_http_rows(path: Path) -> list[PreparedTrainingRow]:
    """Load HTTP CSIC 2010 requests into MIRAGE's runtime feature contract."""
    return _csic_http_rows(load_csic_http_directory(path))


def load_dataset(path: Path, source_kind: DatasetSource) -> list[PreparedTrainingRow]:
    """Load source data using the selected adapter."""
    if source_kind == "mirage-jsonl":
        return load_mirage_jsonl(path)
    if source_kind == "api-log-jsonl":
        return load_api_log_jsonl(path)
    if source_kind == "reviewed-api-log-jsonl":
        return load_reviewed_api_log_jsonl(path)
    if source_kind == "csic-http-dir":
        return load_csic_http_rows(path)
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
    rng = random.Random(random_seed)  # noqa: S311 - seeded, reproducible split; not security-sensitive

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
    expected_checksums: dict[str, str] | None = None,
    source_review_path: Path | None = None,
) -> DatasetManifest:
    """Validate, split, and write a versioned training dataset."""
    csic_source: LoadedCSICHTTP | None = None
    api_log_source_review: dict | None = None
    if source_kind == "csic-http-dir":
        if source_review_path is not None:
            raise DatasetValidationError(
                "source_review_path is only supported for reviewed-api-log-jsonl"
            )
        csic_source = load_csic_http_directory(
            input_path,
            expected_checksums=expected_checksums,
        )
        rows = _csic_http_rows(csic_source)
    elif source_kind == "reviewed-api-log-jsonl":
        if expected_checksums:
            raise DatasetValidationError(
                "expected_checksums is only supported for csic-http-dir"
            )
        if source_review_path is None:
            raise DatasetValidationError(
                "API log source review is required for reviewed-api-log-jsonl"
            )
        api_log_source_review = validate_api_log_source_review(
            source_review_path,
            input_path,
        )
        rows = load_reviewed_api_log_jsonl(input_path)
        if len(rows) != api_log_source_review.get("accepted_rows"):
            raise DatasetValidationError(
                "API log accepted row count does not match its source review"
            )
    else:
        if expected_checksums:
            raise DatasetValidationError(
                "expected_checksums is only supported for csic-http-dir"
            )
        if source_review_path is not None:
            raise DatasetValidationError(
                "source_review_path is only supported for reviewed-api-log-jsonl"
            )
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
    copied_source_review_path = output_dir / "source-review.json"

    write_jsonl(train_path, train_rows)
    write_jsonl(test_path, test_rows)
    if source_review_path is not None:
        shutil.copyfile(source_review_path, copied_source_review_path)

    label_counts = Counter(row.label for row in rows)
    train_label_counts = Counter(row.label for row in train_rows)
    test_label_counts = Counter(row.label for row in test_rows)
    files = {
        "train": train_path.name,
        "test": test_path.name,
        "manifest": manifest_path.name,
    }
    file_sha256 = {
        "train": sha256_file(train_path),
        "test": sha256_file(test_path),
    }
    if api_log_source_review is not None:
        files["source_review"] = copied_source_review_path.name
        file_sha256["source_review"] = sha256_file(copied_source_review_path)

    input_sha256: dict[str, str] = {}
    duplicate_rows_removed = 0
    rejected_rows = 0
    if csic_source is not None:
        input_sha256 = csic_source.input_sha256
        duplicate_rows_removed = csic_source.duplicate_rows_removed
    elif api_log_source_review is not None:
        input_sha256 = {
            input_path.name: str(api_log_source_review["input_sha256"])
        }
        duplicate_rows_removed = int(
            api_log_source_review["duplicate_rows_removed"]
        )
        rejected_rows = int(api_log_source_review["rejected_rows"])

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
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        feature_names=list(FEATURE_NAMES),
        files=files,
        file_sha256=file_sha256,
        source_url=CSIC_SOURCE_URL if csic_source else None,
        distribution_url=CSIC_DISTRIBUTION_URL if csic_source else None,
        input_sha256=input_sha256,
        duplicate_rows_removed=duplicate_rows_removed,
        rejected_rows=rejected_rows,
    )

    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


