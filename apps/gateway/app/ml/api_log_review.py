"""Privacy-safe review reports for labeled custom API logs."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.ml.errors import DatasetValidationError
from app.schemas.request import InspectRequest
from app.services.feature_extraction import (
    FEATURE_CONTRACT_VERSION,
    FeatureVector,
    extract_features,
)

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    # Imported lazily so the existing dataset adapter remains the single parser.
    from app.ml.datasets import (  # pylint: disable=import-outside-toplevel
        API_LOG_LABEL_FIELDS,
        _api_log_request,
        _first_object_value,
        _label_from_api_log,
    )

    label = _label_from_api_log(
        _first_object_value(record, *API_LOG_LABEL_FIELDS),
        line_number=line_number,
    )
    return label, _api_log_request(record, line_number=line_number)


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
    input_sha256 = _sha256_file(path)
    labels_by_identity: dict[str, int] = {}
    rows_by_identity: dict[str, ReviewedAPILogRow] = {}

    with path.open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            if not raw_line.strip():
                continue
            if len(raw_line) > MAX_API_LOG_LINE_BYTES:
                raise DatasetValidationError(
                    f"API log row exceeds {MAX_API_LOG_LINE_BYTES} bytes on line "
                    f"{line_number}"
                )
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise DatasetValidationError(
                    f"API log row is not UTF-8 on line {line_number}"
                ) from exc
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

            label, request = _parse_record(record, line_number=line_number)
            identity = _request_identity(request)
            previous_label = labels_by_identity.get(identity)
            if previous_label is not None:
                if previous_label != label:
                    raise DatasetValidationError(
                        "API log source contains conflicting labels for one "
                        "request identity"
                    )
                continue

            source_id = (
                record.get("event_id")
                or record.get("request_id")
                or record.get("id")
                or line_number
            )
            labels_by_identity[identity] = label
            rows_by_identity[identity] = ReviewedAPILogRow(
                features=extract_features(request),
                label=label,
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

    with path.open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            if not raw_line.strip():
                continue
            total_rows += 1
            if len(raw_line) > MAX_API_LOG_LINE_BYTES:
                rejection_reasons["line_too_large"] += 1
                continue
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                rejection_reasons["invalid_utf8"] += 1
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                rejection_reasons["invalid_json"] += 1
                continue
            if not isinstance(record, dict):
                rejection_reasons["row_not_object"] += 1
                continue
            try:
                label, request = _parse_record(record, line_number=line_number)
            except (DatasetValidationError, ValueError):
                rejection_reasons["invalid_request_or_label"] += 1
                continue

            identity = _request_identity(request)
            previous_label = labels_by_identity.get(identity)
            if previous_label is None:
                labels_by_identity[identity] = label
            elif previous_label == label:
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
        input_sha256=_sha256_file(path),
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
    if _sha256_file(input_path) != expected_sha256:
        raise DatasetValidationError(
            "API log source review SHA-256 does not match input"
        )
    return review
