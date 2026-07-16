"""Lossless parser and provenance loader for the HTTP CSIC 2010 dataset."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from app.ml.errors import DatasetValidationError

CSIC_SOURCE_URL = "https://www.impactcybertrust.org/dataset_view?idDataset=940"
CSIC_DISTRIBUTION_URL = "https://doi.org/10.60895/redata/RWUUSV"
CSIC_FILE_LABELS = {
    "normalTrafficTraining.txt": 0,
    "normalTrafficTest.txt": 0,
    "anomalousTrafficTest.txt": 1,
}


@dataclass(frozen=True)
class CSICHTTPRequest:
    """One parsed HTTP request with its source label and stable identity."""

    method: str
    path: str
    query: str
    user_agent: str
    body: bytes
    destination_port: int
    label: int
    source_file: str
    record_id: str


@dataclass(frozen=True)
class LoadedCSICHTTP:
    """Parsed records and reproducible input provenance."""

    records: list[CSICHTTPRequest]
    input_sha256: dict[str, str]
    duplicate_rows_removed: int
    rejected_rows: int = 0


def _header_end(payload: bytes, start: int) -> tuple[int, int]:
    first_newline = payload.find(b"\n", start)
    if first_newline < 0:
        raise DatasetValidationError("HTTP request headers are truncated")
    marker = b"\r\n\r\n" if payload[first_newline - 1 : first_newline] == b"\r" else b"\n\n"
    index = payload.find(marker, first_newline)
    if index < 0:
        raise DatasetValidationError("HTTP request headers are truncated")
    return index, len(marker)


def _request_identity(method: str, target: str, user_agent: str, body: bytes) -> str:
    canonical = (
        f"{method.upper()} {target}\nuser-agent:{user_agent}\n".encode("latin-1")
        + body
    )
    return hashlib.sha256(canonical).hexdigest()


def parse_csic_http_requests(
    payload: bytes,
    *,
    source_file: str,
    label: int,
) -> list[CSICHTTPRequest]:
    """Parse concatenated HTTP/1.x requests using each declared body length."""
    if not payload.strip():
        raise DatasetValidationError(f"CSIC source file is empty: {source_file}")

    records: list[CSICHTTPRequest] = []
    cursor = 0
    while cursor < len(payload):
        while cursor < len(payload) and payload[cursor] in b"\r\n\t ":
            cursor += 1
        if cursor >= len(payload):
            break

        header_end, delimiter_size = _header_end(payload, cursor)
        header_block = payload[cursor:header_end].decode("latin-1")
        lines = header_block.replace("\r\n", "\n").split("\n")
        request_line = lines[0].split(" ", 2)
        if len(request_line) != 3 or not request_line[2].startswith("HTTP/"):
            raise DatasetValidationError(
                f"invalid HTTP request line in {source_file}: {lines[0]!r}"
            )
        method, target, _protocol = request_line
        if not method.isalpha():
            raise DatasetValidationError(
                f"invalid HTTP method in {source_file}: {method!r}"
            )

        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line:
                continue
            if ":" not in line:
                raise DatasetValidationError(
                    f"invalid HTTP header in {source_file}: {line!r}"
                )
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

        content_length_value = headers.get("content-length", "0")
        try:
            content_length = int(content_length_value)
        except ValueError as exc:
            raise DatasetValidationError(
                f"invalid Content-Length in {source_file}"
            ) from exc
        if content_length < 0:
            raise DatasetValidationError(f"invalid Content-Length in {source_file}")

        body_start = header_end + delimiter_size
        body_end = body_start + content_length
        if body_end > len(payload):
            raise DatasetValidationError(f"truncated body in {source_file}")
        body = payload[body_start:body_end]

        parsed_target = urlsplit(target)
        path = parsed_target.path or "/"
        query = parsed_target.query
        host = parsed_target.hostname or headers.get("host", "").split(":", 1)[0]
        try:
            port = parsed_target.port
        except ValueError:
            port = None
        if port is None and ":" in headers.get("host", ""):
            try:
                port = int(headers["host"].rsplit(":", 1)[1])
            except ValueError:
                port = None
        if not host:
            raise DatasetValidationError(f"HTTP request is missing Host in {source_file}")

        records.append(
            CSICHTTPRequest(
                method=method.upper(),
                path=path,
                query=query,
                user_agent=headers.get("user-agent", ""),
                body=body,
                destination_port=port or (443 if parsed_target.scheme == "https" else 80),
                label=label,
                source_file=source_file,
                record_id=_request_identity(method, target, headers.get("user-agent", ""), body),
            )
        )
        cursor = body_end

    if not records:
        raise DatasetValidationError(f"no HTTP requests found in {source_file}")
    return records


def load_csic_http_directory(
    path: Path,
    *,
    expected_checksums: dict[str, str] | None = None,
) -> LoadedCSICHTTP:
    """Load the three official CSIC subsets and remove repeated request identities."""
    if not path.is_dir():
        raise DatasetValidationError(f"CSIC source directory not found: {path}")

    available = {item.name: item for item in path.iterdir() if item.is_file()}
    missing = sorted(set(CSIC_FILE_LABELS) - set(available))
    if missing:
        raise DatasetValidationError(
            f"CSIC source directory is missing required files: {', '.join(missing)}"
        )
    if expected_checksums is not None and set(expected_checksums) != set(
        CSIC_FILE_LABELS
    ):
        raise DatasetValidationError(
            "CSIC checksums must cover the three required files exactly"
        )

    checksums: dict[str, str] = {}
    records_by_id: dict[str, CSICHTTPRequest] = {}
    duplicates = 0
    for name, label in CSIC_FILE_LABELS.items():
        data = available[name].read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        checksums[name] = digest
        expected = (expected_checksums or {}).get(name)
        if expected is not None and digest.lower() != expected.lower():
            raise DatasetValidationError(f"checksum mismatch for {name}")

        for record in parse_csic_http_requests(data, source_file=name, label=label):
            previous = records_by_id.get(record.record_id)
            if previous is not None:
                if previous.label != record.label:
                    raise DatasetValidationError(
                        f"duplicate request has conflicting labels in {name}"
                    )
                duplicates += 1
                continue
            records_by_id[record.record_id] = record

    return LoadedCSICHTTP(
        records=list(records_by_id.values()),
        input_sha256=checksums,
        duplicate_rows_removed=duplicates,
    )
