"""Dataset validation and preparation helpers for MIRAGE model training."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal
from urllib.parse import urlsplit

from app.schemas.request import InspectRequest
from app.services.feature_extraction import FEATURE_NAMES, FeatureVector, extract_features


DatasetSource = Literal["mirage-jsonl", "api-log-jsonl", "cicids-csv"]


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


@dataclass(frozen=True)
class DatasetReview:
    """Review result for deciding whether a prepared split is trainable."""

    manifest_path: str
    ready_for_training: bool
    dataset_name: str
    dataset_version: str
    source_kind: str
    total_rows: int
    train_rows: int
    test_rows: int
    label_counts: dict[str, int]
    train_label_counts: dict[str, int]
    test_label_counts: dict[str, int]
    blockers: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


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
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            location = f" on line {line_number}" if line_number else ""
            raise DatasetValidationError(
                f"feature {name!r} must be numeric{location}"
            ) from exc
        normalized[name] = numeric_value if math.isfinite(numeric_value) else 0.0
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
    normalized_row = {key.strip(): value for key, value in row.items()}
    for name in names:
        value = normalized_row.get(name)
        if value != "":
            return value
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


API_LOG_LABELS = {
    "0": 0,
    "normal": 0,
    "benign": 0,
    "allow": 0,
    "allowed": 0,
    "clean": 0,
    "ok": 0,
    "pass": 0,
    "false_positive": 0,
    "1": 1,
    "suspicious": 1,
    "malicious": 1,
    "attack": 1,
    "monitor": 1,
    "redirect_to_decoy": 1,
    "false_negative": 1,
    "true_positive": 1,
    "deny": 1,
    "denied": 1,
    "blocked": 1,
    "redirected": 1,
    "decoy": 1,
    "threat": 1,
}

API_LOG_LABEL_FIELDS = (
    "label",
    "analyst_label",
    "class",
    "decision",
    "outcome",
    "verdict",
    "classification",
)


def _label_from_api_log(value: object, *, line_number: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in {0, 1}:
        return value
    if isinstance(value, str):
        normalized = API_LOG_LABELS.get(value.strip().lower())
        if normalized is not None:
            return normalized
    raise DatasetValidationError(
        f"API log label must be normal/suspicious or 0/1 on line {line_number}"
    )


def _first_object_value(record: dict, *names: str) -> object:
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return None


def _headers_value(record: dict, *names: str) -> object:
    headers = record.get("headers")
    if not isinstance(headers, dict):
        return None

    normalized_headers = {str(key).lower(): value for key, value in headers.items()}
    for name in names:
        value = normalized_headers.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _request_object(record: dict) -> dict:
    for name in ("request", "http_request", "httpRequest", "http"):
        value = record.get(name)
        if isinstance(value, dict):
            return value
    return record


def _path_from_value(value: object) -> str:
    if value in (None, ""):
        return ""
    raw_path = str(value)
    parsed = urlsplit(raw_path)
    if parsed.scheme and parsed.netloc:
        return parsed.path or "/"
    if "?" in raw_path:
        return raw_path.split("?", 1)[0] or "/"
    return raw_path


def _payload_excerpt(request_data: dict) -> str:
    value = _first_object_value(
        request_data,
        "payload_excerpt",
        "body_excerpt",
        "request_body",
        "body",
        "payload",
        "query",
        "query_string",
    )
    return str(value or "")[:4096]


def _api_payload_indicators(value: object, *, line_number: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise DatasetValidationError(
        f"payload_indicators must be a list of strings on line {line_number}"
    )


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _api_log_request(record: dict, *, line_number: int) -> InspectRequest:
    request_data = _request_object(record)
    user_agent = _first_object_value(
        request_data,
        "user_agent",
        "userAgent",
        "ua",
        "user-agent",
    ) or _headers_value(request_data, "user-agent")
    try:
        return InspectRequest(
            ip_address=str(
                _first_object_value(
                    request_data,
                    "ip_address",
                    "source_ip",
                    "client_ip",
                    "src_ip",
                    "remote_addr",
                    "remoteAddress",
                    "clientIp",
                )
                or ""
            ),
            method=str(
                _first_object_value(
                    request_data,
                    "method",
                    "http_method",
                    "httpMethod",
                    "request_method",
                )
                or ""
            ),
            path=_path_from_value(
                _first_object_value(
                    request_data,
                    "path",
                    "endpoint",
                    "url_path",
                    "route",
                    "uri",
                    "url",
                    "request_uri",
                )
            ),
            user_agent=str(user_agent or ""),
            request_count=_optional_int(
                _first_object_value(
                    request_data,
                    "request_count",
                    "source_request_count",
                    "count",
                    "hits",
                )
            )
            or 1,
            payload_indicators=_api_payload_indicators(
                _first_object_value(
                    request_data,
                    "payload_indicators",
                    "indicators",
                    "signals",
                    "tags",
                ),
                line_number=line_number,
            ),
            payload_excerpt=_payload_excerpt(request_data),
            timestamp=request_data.get("timestamp"),
            flow_duration_ms=_optional_float(
                _first_object_value(
                    request_data,
                    "flow_duration_ms",
                    "duration_ms",
                    "durationMs",
                    "latency_ms",
                )
            ),
            flow_packets_per_second=_optional_float(
                _first_object_value(
                    request_data,
                    "flow_packets_per_second",
                    "flowPacketsPerSecond",
                    "packets_per_second",
                )
            ),
            packet_length_mean=_optional_float(
                _first_object_value(
                    request_data,
                    "packet_length_mean",
                    "packetLengthMean",
                    "avg_packet_length",
                )
            ),
            syn_flag_count=_optional_int(
                _first_object_value(request_data, "syn_flag_count", "synFlagCount")
            ),
            destination_port=_optional_int(
                _first_object_value(
                    request_data,
                    "destination_port",
                    "destinationPort",
                    "dst_port",
                    "port",
                )
            ),
            average_packet_size=_optional_float(
                _first_object_value(
                    request_data,
                    "average_packet_size",
                    "averagePacketSize",
                    "avg_packet_size",
                )
            ),
        )
    except ValueError as exc:
        raise DatasetValidationError(
            f"invalid API log request fields on line {line_number}"
        ) from exc


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
    if source_kind == "api-log-jsonl":
        return load_api_log_jsonl(path)
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


def _load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetValidationError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetValidationError("manifest is not valid JSON") from exc
    if not isinstance(data, dict):
        raise DatasetValidationError("manifest must be a JSON object")
    return data


def _count_jsonl(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as source:
            return sum(1 for line in source if line.strip())
    except FileNotFoundError as exc:
        raise DatasetValidationError(f"prepared file not found: {path}") from exc


def _manifest_int(manifest: dict, key: str, blockers: list[str]) -> int:
    try:
        return int(manifest.get(key) or 0)
    except (TypeError, ValueError):
        blockers.append(f"manifest {key} must be an integer")
        return 0


def _manifest_counts(manifest: dict, key: str, blockers: list[str]) -> dict[str, int]:
    raw_counts = manifest.get(key) or {}
    if not isinstance(raw_counts, dict):
        blockers.append(f"manifest {key} must be an object")
        return {}

    counts: dict[str, int] = {}
    for label, count in raw_counts.items():
        try:
            counts[str(label)] = int(count)
        except (TypeError, ValueError):
            blockers.append(f"manifest {key}.{label} must be an integer")
            counts[str(label)] = 0
    return counts


def review_prepared_dataset(
    manifest_path: Path,
    *,
    min_total_rows: int = 20,
    min_train_rows: int = 15,
    min_test_rows: int = 5,
    min_rows_per_class: int = 2,
) -> DatasetReview:
    """Review a prepared dataset manifest before training."""
    blockers: list[str] = []
    warnings: list[str] = []
    manifest = _load_manifest(manifest_path)
    base_dir = manifest_path.parent
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        files = {}
        blockers.append("manifest files must be an object")

    train_file = files.get("train")
    test_file = files.get("test")
    if not isinstance(train_file, str):
        blockers.append("manifest is missing train file")
    if not isinstance(test_file, str):
        blockers.append("manifest is missing test file")

    train_rows_actual = (
        _count_jsonl(base_dir / train_file) if isinstance(train_file, str) else 0
    )
    test_rows_actual = (
        _count_jsonl(base_dir / test_file) if isinstance(test_file, str) else 0
    )

    total_rows = _manifest_int(manifest, "total_rows", blockers)
    train_rows = _manifest_int(manifest, "train_rows", blockers)
    test_rows = _manifest_int(manifest, "test_rows", blockers)
    label_counts = _manifest_counts(manifest, "label_counts", blockers)
    train_label_counts = _manifest_counts(manifest, "train_label_counts", blockers)
    test_label_counts = _manifest_counts(manifest, "test_label_counts", blockers)

    if total_rows < min_total_rows:
        blockers.append(f"Total rows {total_rows} is below {min_total_rows}")
    if train_rows < min_train_rows:
        blockers.append(f"Train rows {train_rows} is below {min_train_rows}")
    if test_rows < min_test_rows:
        blockers.append(f"Test rows {test_rows} is below {min_test_rows}")
    if train_rows_actual != train_rows:
        blockers.append(
            f"Train file row count {train_rows_actual} does not match manifest {train_rows}"
        )
    if test_rows_actual != test_rows:
        blockers.append(
            f"Test file row count {test_rows_actual} does not match manifest {test_rows}"
        )

    for label in ("0", "1"):
        if label_counts.get(label, 0) < min_rows_per_class:
            blockers.append(f"Label {label} has fewer than {min_rows_per_class} rows")
        if train_label_counts.get(label, 0) < 1:
            blockers.append(f"Train split is missing label {label}")
        if test_label_counts.get(label, 0) < 1:
            blockers.append(f"Test split is missing label {label}")

    if tuple(manifest.get("feature_names", ())) != FEATURE_NAMES:
        blockers.append("Feature contract does not match the gateway")
    if total_rows and total_rows < 100:
        warnings.append("Dataset is small; keep any trained artifact in shadow mode")

    return DatasetReview(
        manifest_path=str(manifest_path),
        ready_for_training=not blockers,
        dataset_name=str(manifest.get("dataset_name") or ""),
        dataset_version=str(manifest.get("dataset_version") or ""),
        source_kind=str(manifest.get("source_kind") or ""),
        total_rows=total_rows,
        train_rows=train_rows,
        test_rows=test_rows,
        label_counts=label_counts,
        train_label_counts=train_label_counts,
        test_label_counts=test_label_counts,
        blockers=blockers,
        warnings=warnings,
    )
