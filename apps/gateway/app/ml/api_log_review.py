"""Privacy-safe review reports for labeled custom API logs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from app.ml.artifact_integrity import sha256_file
from app.ml.errors import DatasetValidationError
from app.schemas.request import InspectRequest
from app.services.feature_extraction import (
    FEATURE_CONTRACT_VERSION,
    FeatureVector,
    extract_features,
)
from app.services.payload_signals import build_payload_excerpt

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
        )
    except ValueError as exc:
        raise DatasetValidationError(
            f"invalid API log request fields on line {line_number}"
        ) from exc


MAX_API_LOG_LINE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class APILogReviewMetadata:
    """Operator-supplied provenance without raw request content."""

    data_origin: str
    collection_started_at: str
    collection_ended_at: str
    labeling_method: str
    sanitized: bool
    approved_for_training: bool


@dataclass(frozen=True)
class APILogSourceReview:
    """Sanitized source quality report bound to one input file."""

    review_version: int
    source_kind: str
    generated_at: str
    input_file: str
    input_sha256: str
    feature_contract_version: int
    metadata: APILogReviewMetadata
    total_rows: int
    accepted_rows: int
    duplicate_rows_removed: int
    rejected_rows: int
    conflicting_identities: int
    label_counts: dict[str, int]
    rejection_reasons: dict[str, int]
    ready_for_preparation: bool
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewedAPILogRow:
    """One deduplicated row safe to persist in a prepared split."""

    features: FeatureVector
    label: int
    record_id: str


def _metadata_blockers(metadata: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    data_origin = metadata.get("data_origin")
    labeling_method = metadata.get("labeling_method")
    if not isinstance(data_origin, str) or not data_origin.strip():
        blockers.append("Data origin must not be empty")
    if not isinstance(labeling_method, str) or not labeling_method.strip():
        blockers.append("Labeling method must not be empty")
    try:
        started_value = metadata.get("collection_started_at")
        ended_value = metadata.get("collection_ended_at")
        if not isinstance(started_value, str) or not isinstance(ended_value, str):
            raise ValueError
        started_at = datetime.fromisoformat(started_value.replace("Z", "+00:00"))
        ended_at = datetime.fromisoformat(ended_value.replace("Z", "+00:00"))
        if started_at.tzinfo is None or ended_at.tzinfo is None:
            raise ValueError
        if ended_at < started_at:
            blockers.append("API log collection window ends before it starts")
    except (TypeError, ValueError):
        blockers.append("API log collection window must use timezone-aware ISO-8601")
    return blockers


def _review_counts_are_consistent(review: dict[str, Any]) -> bool:
    keys = (
        "total_rows",
        "accepted_rows",
        "duplicate_rows_removed",
        "rejected_rows",
        "conflicting_identities",
    )
    values = {key: review.get(key) for key in keys}
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in values.values()
    ):
        return False
    if values["rejected_rows"] or values["conflicting_identities"]:
        return False
    if values["total_rows"] != (
        values["accepted_rows"] + values["duplicate_rows_removed"]
    ):
        return False

    label_counts = review.get("label_counts")
    if not isinstance(label_counts, dict) or set(label_counts) != {"0", "1"}:
        return False
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in label_counts.values()
    ):
        return False
    return sum(label_counts.values()) == values["accepted_rows"]


def api_log_source_review_errors(review: dict[str, Any]) -> list[str]:
    """Return structural blockers for a report, independent of its raw source."""
    errors: list[str] = []
    if review.get("review_version") != 1:
        errors.append("review version is unsupported")
    if review.get("source_kind") != "reviewed-api-log-jsonl":
        errors.append("source kind is invalid")
    if review.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
        errors.append("feature contract does not match the gateway")

    generated_at = review.get("generated_at")
    try:
        if not isinstance(generated_at, str):
            raise ValueError
        generated_timestamp = datetime.fromisoformat(
            generated_at.replace("Z", "+00:00")
        )
        if generated_timestamp.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("generated timestamp must use timezone-aware ISO-8601")

    input_file = review.get("input_file")
    if (
        not isinstance(input_file, str)
        or not input_file.strip()
        or Path(input_file).name != input_file
    ):
        errors.append("input filename is invalid")
    input_sha256 = review.get("input_sha256")
    if not isinstance(input_sha256, str) or re.fullmatch(
        r"[0-9a-f]{64}", input_sha256
    ) is None:
        errors.append("SHA-256 is invalid")

    metadata = review.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata is invalid")
    else:
        errors.extend(_metadata_blockers(metadata))
        if metadata.get("sanitized") is not True:
            errors.append("source is not sanitized")
        if metadata.get("approved_for_training") is not True:
            errors.append("source is not approved for training")

    blockers = review.get("blockers")
    if review.get("ready_for_preparation") is not True:
        errors.append("source review is not ready for preparation")
    if not isinstance(blockers, list) or blockers:
        errors.append("source review blockers must be an empty list")
    if not _review_counts_are_consistent(review):
        errors.append("row counts are inconsistent")

    rejection_reasons = review.get("rejection_reasons")
    if not isinstance(rejection_reasons, dict) or any(
        not isinstance(reason, str)
        or not reason
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        for reason, count in (
            rejection_reasons.items()
            if isinstance(rejection_reasons, dict)
            else ()
        )
    ):
        errors.append("rejection reasons are invalid")
    elif sum(rejection_reasons.values()) != review.get("rejected_rows"):
        errors.append("rejection reason counts are inconsistent")
    return errors


def _parse_record(record: dict, *, line_number: int) -> tuple[int, InspectRequest]:
    label = _label_from_api_log(
        _first_object_value(record, *API_LOG_LABEL_FIELDS),
        line_number=line_number,
    )
    return label, _api_log_request(record, line_number=line_number)


@dataclass(frozen=True)
class _ParsedLine:
    """One non-blank API-log line: a parsed request, or why it was rejected."""

    line_number: int
    record: dict = field(default_factory=dict)
    label: int = 0
    request: InspectRequest | None = None
    rejection: str | None = None
    error: Exception | None = None


def _parse_api_log_line(raw_line: bytes, line_number: int) -> _ParsedLine:
    def rejected(reason: str, message: str) -> _ParsedLine:
        error = DatasetValidationError(f"{message} on line {line_number}")
        return _ParsedLine(line_number, rejection=reason, error=error)

    if len(raw_line) > MAX_API_LOG_LINE_BYTES:
        return rejected(
            "line_too_large", f"API log row exceeds {MAX_API_LOG_LINE_BYTES} bytes"
        )
    try:
        record = json.loads(raw_line.decode("utf-8"))
    except UnicodeDecodeError:
        return rejected("invalid_utf8", "API log row is not UTF-8")
    except json.JSONDecodeError:
        return rejected("invalid_json", "invalid JSON")
    if not isinstance(record, dict):
        return rejected("row_not_object", "API log row must be an object")
    try:
        label, request = _parse_record(record, line_number=line_number)
    except (DatasetValidationError, ValueError) as exc:
        return _ParsedLine(line_number, rejection="invalid_request_or_label", error=exc)
    return _ParsedLine(line_number, record, label, request)


def _parse_api_log_lines(path: Path) -> Iterator[_ParsedLine]:
    """Parse every non-blank line; rejected lines carry a reason and an error."""
    with path.open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            if raw_line.strip():
                yield _parse_api_log_line(raw_line, line_number)


def _request_identity(request: InspectRequest) -> str:
    identity = request.model_dump(
        mode="json",
        exclude={"ip_address", "timestamp"},
    )
    identity["payload_indicators"] = sorted(identity["payload_indicators"])
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hashed_record_id(
    *,
    input_sha256: str,
    source_id: object,
    identity: str,
) -> str:
    value = f"{input_sha256}:{source_id}:{identity}"
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_reviewed_api_log_rows(path: Path) -> list[ReviewedAPILogRow]:
    """Load deduplicated API-log rows without persisting raw identifiers."""
    input_sha256 = sha256_file(path)
    labels_by_identity: dict[str, int] = {}
    rows_by_identity: dict[str, ReviewedAPILogRow] = {}

    for row in _parse_api_log_lines(path):
        if row.error is not None:
            raise row.error
        identity = _request_identity(row.request)
        previous_label = labels_by_identity.get(identity)
        if previous_label is not None:
            if previous_label != row.label:
                raise DatasetValidationError(
                    "API log source contains conflicting labels for one "
                    "request identity"
                )
            continue

        source_id = (
            row.record.get("event_id")
            or row.record.get("request_id")
            or row.record.get("id")
            or row.line_number
        )
        labels_by_identity[identity] = row.label
        rows_by_identity[identity] = ReviewedAPILogRow(
            features=extract_features(row.request),
            label=row.label,
            record_id=_hashed_record_id(
                input_sha256=input_sha256,
                source_id=source_id,
                identity=identity,
            ),
        )

    return list(rows_by_identity.values())


def review_api_log_source(
    path: Path,
    metadata: APILogReviewMetadata,
    *,
    minimum_rows: int = 20,
    minimum_rows_per_class: int = 2,
) -> APILogSourceReview:
    """Review a labeled JSONL source without retaining request content."""
    total_rows = 0
    duplicate_rows_removed = 0
    rejection_reasons: Counter[str] = Counter()
    labels_by_identity: dict[str, int] = {}
    conflicting_identities: set[str] = set()

    for row in _parse_api_log_lines(path):
        total_rows += 1
        if row.rejection is not None:
            rejection_reasons[row.rejection] += 1
            continue

        identity = _request_identity(row.request)
        previous_label = labels_by_identity.get(identity)
        if previous_label is None:
            labels_by_identity[identity] = row.label
        elif previous_label == row.label:
            duplicate_rows_removed += 1
        else:
            conflicting_identities.add(identity)

    label_counts = Counter(labels_by_identity.values())
    accepted_rows = len(labels_by_identity)
    rejected_rows = sum(rejection_reasons.values())
    blockers = _metadata_blockers(asdict(metadata))
    if not metadata.sanitized:
        blockers.append("Source must be sanitized before preparation")
    if not metadata.approved_for_training:
        blockers.append("Source must be approved for training")
    if rejected_rows:
        blockers.append(f"{rejected_rows} API log row(s) were rejected")
    if conflicting_identities:
        blockers.append(
            f"{len(conflicting_identities)} request identity or identities have "
            "conflicting labels"
        )
    if accepted_rows < minimum_rows:
        blockers.append(f"Accepted rows {accepted_rows} is below {minimum_rows}")
    for label in (0, 1):
        if label_counts[label] < minimum_rows_per_class:
            blockers.append(
                f"Label {label} has fewer than {minimum_rows_per_class} accepted rows"
            )

    return APILogSourceReview(
        review_version=1,
        source_kind="reviewed-api-log-jsonl",
        generated_at=datetime.now(timezone.utc).isoformat(),
        input_file=path.name,
        input_sha256=sha256_file(path),
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        metadata=metadata,
        total_rows=total_rows,
        accepted_rows=accepted_rows,
        duplicate_rows_removed=duplicate_rows_removed,
        rejected_rows=rejected_rows,
        conflicting_identities=len(conflicting_identities),
        label_counts={str(label): label_counts[label] for label in (0, 1)},
        rejection_reasons=dict(sorted(rejection_reasons.items())),
        ready_for_preparation=not blockers,
        blockers=blockers,
    )


def write_api_log_source_review(path: Path, review: APILogSourceReview) -> None:
    """Write a sanitized source review as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(review.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_api_log_source_review(review_path: Path, input_path: Path) -> dict:
    """Validate a ready review against the exact input selected for preparation."""
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetValidationError(
            f"API log source review not found: {review_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DatasetValidationError("API log source review is not valid JSON") from exc
    if not isinstance(review, dict):
        raise DatasetValidationError("API log source review must be a JSON object")

    review_errors = api_log_source_review_errors(review)
    if review_errors:
        raise DatasetValidationError(
            "API log source review is invalid: " + "; ".join(review_errors)
        )
    if review.get("input_file") != input_path.name:
        raise DatasetValidationError(
            "API log source review input filename does not match"
        )

    expected_sha256 = str(review["input_sha256"])
    if sha256_file(input_path) != expected_sha256:
        raise DatasetValidationError(
            "API log source review SHA-256 does not match input"
        )
    return review
