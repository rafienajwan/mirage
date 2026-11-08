"""Review prepared dataset manifests and bind them into artifact lineage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from app.ml.api_log_review import api_log_source_review_errors
from app.ml.artifact_integrity import sha256_file
from app.ml.csic_http import CSIC_DISTRIBUTION_URL, CSIC_FILE_LABELS, CSIC_SOURCE_URL
from app.ml.errors import DatasetValidationError
from app.services.feature_extraction import FEATURE_CONTRACT_VERSION, FEATURE_NAMES


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
    min_train_rows: int = 20,
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
        # The trainer refuses fewer than 2 rows per class (stratified split).
        if train_label_counts.get(label, 0) < 2:
            blockers.append(f"Train split has fewer than 2 rows of label {label}")
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
