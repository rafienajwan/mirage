"""Tests for deterministic ML feature extraction."""

from app.schemas.request import InspectRequest
from app.services.feature_extraction import extract_features


def test_extract_features_from_suspicious_request():
    request = InspectRequest(
        ip_address="10.0.0.2",
        method="POST",
        path="/.env",
        user_agent="sqlmap/1.8",
        request_count=50,
        payload_indicators=["sql-like", "encoded"],
        flow_duration_ms=250,
        destination_port=443,
    )
    features = extract_features(request)
    assert features["sensitive_path"] == 1.0
    assert features["suspicious_user_agent"] == 1.0
    assert features["high_risk_indicator_count"] == 1.0
    assert features["medium_risk_indicator_count"] == 1.0
    assert features["method_write"] == 1.0
    assert features["flow_duration_ms"] == 250.0
    assert features["destination_port"] == 443.0


def test_extract_features_has_stable_defaults():
    request = InspectRequest(
        ip_address="192.168.1.2", method="GET", path="/api/products"
    )
    features = extract_features(request)
    assert features["method_get"] == 1.0
    assert features["flow_packets_per_second"] == 0.0
    assert all(isinstance(value, float) for value in features.values())
