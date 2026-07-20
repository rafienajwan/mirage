"""Tests for deterministic ML feature extraction."""

import math

from app.schemas.request import InspectRequest
from app.services.feature_extraction import extract_features
from app.services.payload_signals import build_payload_excerpt


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
    assert features["payload_length_log"] == 0.0
    assert features["payload_entropy"] == 0.0
    assert features["payload_non_alnum_ratio"] == 0.0
    assert features["payload_percent_encoded_count_log"] == 0.0
    assert features["payload_parameter_count_log"] == 0.0
    assert all(isinstance(value, float) for value in features.values())


def test_build_payload_excerpt_combines_and_bounds_query_and_body():
    assert build_payload_excerpt("page=1", "role=admin") == "page=1\nrole=admin"
    assert build_payload_excerpt("", "body") == "body"
    assert build_payload_excerpt("query", "") == "query"
    assert len(build_payload_excerpt("q" * 4096, "body")) == 4096


def test_extract_features_describes_payload_shape_without_raw_content():
    request = InspectRequest(
        ip_address="10.0.0.3",
        method="POST",
        path="/api/search",
        payload_excerpt="a=1&b=%2e%2e",
    )

    features = extract_features(request)

    assert features["payload_length_log"] == round(
        math.log1p(len(request.payload_excerpt)),
        6,
    )
    assert features["payload_entropy"] > 0.0
    assert features["payload_non_alnum_ratio"] == round(5 / 12, 6)
    assert features["payload_percent_encoded_count_log"] == round(math.log1p(2), 6)
    assert features["payload_parameter_count_log"] == round(math.log1p(2), 6)
    assert request.payload_excerpt not in features


def test_extract_features_uses_shannon_entropy_per_character():
    request = InspectRequest(
        ip_address="10.0.0.4",
        method="POST",
        path="/api/search",
        payload_excerpt="ab",
    )

    features = extract_features(request)

    assert features["payload_entropy"] == 1.0
