"""Tests for the offline payload-detection evaluation script."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_payload_detection import evaluate  # noqa: E402

from app.ml.csic_http import CSICHTTPRequest  # noqa: E402


def _record(body: bytes, label: int) -> CSICHTTPRequest:
    return CSICHTTPRequest(
        method="POST",
        path="/tienda1/publico/anadir.jsp",
        query="",
        user_agent="Mozilla/5.0",
        body=body,
        destination_port=8080,
        label=label,
        source_file="fixture",
        record_id=f"r{label}",
    )


def test_evaluate_counts_shares():
    result = evaluate([_record(b"id=1' or 1=1--", 1), _record(b"id=1&cantidad=2", 0)])
    assert result["attack"]["flagged"] == 1.0
    assert result["attack"]["redirect_to_decoy"] == 1.0
    assert result["normal"]["flagged"] == 0.0
    assert result["normal"]["allow"] == 1.0
