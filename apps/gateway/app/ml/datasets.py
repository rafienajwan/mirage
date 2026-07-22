"""Dataset validation and preparation helpers for MIRAGE model training."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal
from urllib.parse import urlsplit

from app.ml.csic_http import (
    CSIC_DISTRIBUTION_URL,
    CSIC_FILE_LABELS,
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
    "cicids-csv",
    "cicids-csv-dir",
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


def _query_from_value(value: object) -> str:
    if value in (None, ""):
        return ""
    return urlsplit(str(value)).query


def _payload_excerpt(request_data: dict) -> str:
    explicit_excerpt = _first_object_value(request_data, "payload_excerpt")
    if explicit_excerpt not in (None, ""):
        return str(explicit_excerpt)[:4096]

    target = _first_object_value(
        request_data,
        "path",
        "endpoint",
        "url_path",
        "route",
        "uri",
        "url",
        "request_uri",
    )
    query = _first_object_value(request_data, "query", "query_string")
    body = _first_object_value(
        request_data,
        "body_excerpt",
        "request_body",
        "body",
        "payload",
    )
    return build_payload_excerpt(
        str(query or _query_from_value(target)),
        str(body or ""),
    )


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


def load_reviewed_api_log_jsonl(path: Path) -> list[PreparedTrainingRow]:
    """Load deduplicated reviewed logs with privacy-safe record identifiers."""
    from app.ml.api_log_review import load_reviewed_api_log_rows

    return [
        PreparedTrainingRow(
            features=row.features,
            label=row.label,
            source="reviewed-api-log-jsonl",
            record_id=row.record_id,
        )
        for row in load_reviewed_api_log_rows(path)
    ]


def _load_cicids_csv_rows(
    path: Path,
    *,
    source_kind: DatasetSource,
    record_prefix: str | None = None,
) -> list[PreparedTrainingRow]:
    """Load CICIDS-style CSV rows into the MIRAGE feature schema.

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
                    source=source_kind,
                    record_id=(
                        f"{record_prefix}:{line_number}"
                        if record_prefix
                        else str(line_number)
                    ),
                )
            )
    return rows


def load_cicids_csv(path: Path) -> list[PreparedTrainingRow]:
    """Load one CICIDS-style CSV into the MIRAGE feature schema."""
    return _load_cicids_csv_rows(path, source_kind="cicids-csv")


def load_cicids_csv_directory(path: Path) -> list[PreparedTrainingRow]:
    """Load all CICIDS-style CSV files from a directory in stable name order."""
    csv_files = sorted(
        item for item in path.iterdir() if item.suffix.lower() == ".csv"
    )
    if not csv_files:
        raise DatasetValidationError(f"no CSV files found in directory: {path}")

    rows: list[PreparedTrainingRow] = []
    for csv_file in csv_files:
        rows.extend(
            _load_cicids_csv_rows(
                csv_file,
                source_kind="cicids-csv-dir",
                record_prefix=csv_file.name,
            )
        )
    return rows


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
                record.body.decode("latin-1"),
            ),
            destination_port=record.destination_port,
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
    if source_kind == "cicids-csv":
        return load_cicids_csv(path)
    if source_kind == "cicids-csv-dir":
        return load_cicids_csv_directory(path)
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


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a local dataset or manifest file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        from app.ml.api_log_review import validate_api_log_source_review

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
        rejected_rows = csic_source.rejected_rows
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


def _manifest_local_filename(
    files: dict,
    key: str,
    base_dir: Path,
    blockers: list[str],
) -> str | None:
    value = files.get(key)
    if not isinstance(value, str):
        blockers.append(f"manifest is missing {key.replace('_', ' ')} file")
        return None
    candidate = Path(value)
    try:
        stays_local = (
            not candidate.is_absolute()
            and candidate.name == value
            and (base_dir / candidate).resolve().parent == base_dir.resolve()
        )
    except OSError:
        stays_local = False
    if not stays_local:
        blockers.append(
            f"manifest {key.replace('_', ' ')} file must stay in the prepared directory"
        )
        return None
    return value


def _review_csic_provenance(manifest: dict, blockers: list[str]) -> None:
    if manifest.get("source_url") != CSIC_SOURCE_URL:
        blockers.append("CSIC source_url does not match the official catalog")
    if manifest.get("distribution_url") != CSIC_DISTRIBUTION_URL:
        blockers.append("CSIC distribution_url does not match the approved DOI")

    input_sha256 = manifest.get("input_sha256")
    if not isinstance(input_sha256, dict) or set(input_sha256) != set(
        CSIC_FILE_LABELS
    ):
        blockers.append("CSIC input_sha256 must cover the three required files")
    if isinstance(input_sha256, dict):
        for name, checksum in input_sha256.items():
            if not isinstance(checksum, str) or re.fullmatch(
                r"[0-9a-fA-F]{64}", checksum
            ) is None:
                blockers.append(f"CSIC checksum for {name} is invalid")

    for key in ("duplicate_rows_removed", "rejected_rows"):
        try:
            value = int(manifest.get(key, 0))
        except (TypeError, ValueError):
            blockers.append(f"manifest {key} must be a non-negative integer")
            continue
        if value < 0:
            blockers.append(f"manifest {key} must be non-negative")


def _review_api_log_provenance(
    manifest: dict,
    base_dir: Path,
    blockers: list[str],
) -> None:
    files = manifest.get("files")
    if not isinstance(files, dict):
        blockers.append("Reviewed API log manifest files are invalid")
        return
    review_name = _manifest_local_filename(
        files,
        "source_review",
        base_dir,
        blockers,
    )
    if review_name is None:
        return
    try:
        review = json.loads((base_dir / review_name).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        blockers.append("Reviewed API log source review could not be loaded")
        return
    if not isinstance(review, dict):
        blockers.append("Reviewed API log source review must be an object")
        return

    from app.ml.api_log_review import api_log_source_review_errors

    blockers.extend(
        f"Reviewed API log {error}"
        for error in api_log_source_review_errors(review)
    )

    input_file = review.get("input_file")
    input_hash = review.get("input_sha256")
    if (
        not isinstance(input_file, str)
        or not isinstance(input_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", input_hash) is None
        or manifest.get("input_sha256") != {input_file: input_hash}
    ):
        blockers.append("Reviewed API log input provenance does not match manifest")

    expected_counts = {
        "accepted_rows": manifest.get("total_rows"),
        "duplicate_rows_removed": manifest.get("duplicate_rows_removed"),
        "rejected_rows": manifest.get("rejected_rows"),
    }
    if any(review.get(key) != value for key, value in expected_counts.items()):
        blockers.append("Reviewed API log row counts do not match manifest")


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

    train_file = _manifest_local_filename(files, "train", base_dir, blockers)
    test_file = _manifest_local_filename(files, "test", base_dir, blockers)

    train_rows_actual = (
        _count_jsonl(base_dir / train_file) if isinstance(train_file, str) else 0
    )
    test_rows_actual = (
        _count_jsonl(base_dir / test_file) if isinstance(test_file, str) else 0
    )
    expected_hashed_files = {"train", "test"}
    source_review_file: str | None = None
    if manifest.get("source_kind") == "reviewed-api-log-jsonl":
        expected_hashed_files.add("source_review")
        source_review_file = _manifest_local_filename(
            files,
            "source_review",
            base_dir,
            blockers,
        )
    file_sha256 = manifest.get("file_sha256")
    if not isinstance(file_sha256, dict) or set(file_sha256) != expected_hashed_files:
        blockers.append(
            "manifest file_sha256 must cover "
            + ", ".join(sorted(expected_hashed_files))
        )
        file_sha256 = {}

    hashed_files = [("train", train_file), ("test", test_file)]
    if "source_review" in expected_hashed_files:
        hashed_files.append(("source_review", source_review_file))
    for split, filename in hashed_files:
        expected_hash = file_sha256.get(split)
        if not isinstance(expected_hash, str) or re.fullmatch(
            r"[0-9a-fA-F]{64}", expected_hash
        ) is None:
            blockers.append(f"manifest {split} file SHA-256 is invalid")
            continue
        if isinstance(filename, str):
            try:
                matches = sha256_file(base_dir / filename) == expected_hash
            except OSError:
                blockers.append(
                    f"{split.replace('_', ' ').title()} file could not be read"
                )
                continue
            if not matches:
                display_name = split.replace("_", " ").title()
                blockers.append(
                    f"{display_name} file SHA-256 does not match manifest"
                )

    total_rows = _manifest_int(manifest, "total_rows", blockers)
    train_rows = _manifest_int(manifest, "train_rows", blockers)
    test_rows = _manifest_int(manifest, "test_rows", blockers)
    label_counts = _manifest_counts(manifest, "label_counts", blockers)
    train_label_counts = _manifest_counts(manifest, "train_label_counts", blockers)
    test_label_counts = _manifest_counts(manifest, "test_label_counts", blockers)

    if manifest.get("source_kind") == "csic-http-dir":
        _review_csic_provenance(manifest, blockers)
    if manifest.get("source_kind") == "reviewed-api-log-jsonl":
        _review_api_log_provenance(manifest, base_dir, blockers)

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

    if manifest.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
        blockers.append("Feature contract version does not match the gateway")
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


def build_dataset_lineage(
    manifest_path: Path,
    training_path: Path,
) -> dict[str, str]:
    """Build sanitized artifact lineage for a reviewed training split."""
    review = review_prepared_dataset(manifest_path)
    if not review.ready_for_training:
        raise DatasetValidationError(
            "dataset manifest is not ready for training: "
            + "; ".join(review.blockers)
        )

    manifest = _load_manifest(manifest_path)
    files = manifest["files"]
    expected_training_path = (manifest_path.parent / files["train"]).resolve()
    if training_path.resolve() != expected_training_path:
        raise DatasetValidationError("training input is not the manifest train file")

    file_sha256 = manifest["file_sha256"]
    return {
        "dataset_name": review.dataset_name,
        "dataset_version": review.dataset_version,
        "source_kind": review.source_kind,
        "manifest_sha256": sha256_file(manifest_path),
        "train_sha256": str(file_sha256["train"]),
        "test_sha256": str(file_sha256["test"]),
    }
