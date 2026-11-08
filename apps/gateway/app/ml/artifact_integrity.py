"""Pin model artifacts to a SHA-256 digest before they are unpickled.

``joblib.load`` executes code embedded in the file, so a swapped artifact is
code execution in the gateway. Verify the bytes first, then load.
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import re

_DIGEST = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1024 * 1024


class ArtifactIntegrityError(ValueError):
    """The artifact does not match its pinned digest, or the digest is invalid."""


UNPINNED_BLOCKER = "MIRAGE_MODEL_ARTIFACT_SHA256 is not set"


def pinned_digest(settings: object) -> tuple[str | None, bool]:
    """Return (expected digest, may_load) for the configured artifact.

    Outside development an artifact without a pinned digest is never loaded.
    """
    digest = getattr(settings, "ml_model_artifact_sha256", None)
    development = getattr(settings, "app_env", "development") == "development"
    return digest, digest is not None or development


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact_digest(path: Path, expected_sha256: str) -> None:
    expected = expected_sha256.strip().lower()
    if not _DIGEST.fullmatch(expected):
        raise ArtifactIntegrityError("Expected SHA-256 must be 64 hexadecimal characters")
    if not hmac.compare_digest(sha256_file(path), expected):
        raise ArtifactIntegrityError("Artifact SHA-256 does not match the pinned digest")
