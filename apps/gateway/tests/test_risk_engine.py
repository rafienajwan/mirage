"""Tests for risk scoring engine."""

from app.schemas.decision import RiskLevel
from app.schemas.request import InspectRequest
from app.services.risk_engine import calculate_risk


def _make_request(**kwargs) -> InspectRequest:
    defaults = {
        "ip_address": "192.168.1.1",
        "method": "GET",
        "path": "/api/v1/products",
        "user_agent": "Mozilla/5.0",
        "request_count": 1,
        "payload_indicators": [],
    }
    defaults.update(kwargs)
    return InspectRequest(**defaults)


def test_low_risk_normal_request():
    req = _make_request()
    result = calculate_risk(req)
    assert result.score < 30
    assert result.level == RiskLevel.LOW


def test_high_risk_sensitive_path():
    req = _make_request(path="/.env")
    result = calculate_risk(req)
    assert result.score >= 25
    assert any("Sensitive path" in r for r in result.reasons)


def test_high_risk_suspicious_user_agent():
    req = _make_request(user_agent="sqlmap/1.7")
    result = calculate_risk(req)
    assert result.score >= 15
    assert any("user-agent" in r.lower() for r in result.reasons)


def test_high_risk_payload_indicators():
    req = _make_request(payload_indicators=["sql-like", "path-traversal"])
    result = calculate_risk(req)
    assert result.score >= 40
    assert result.level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_critical_risk_combined():
    req = _make_request(
        path="/admin",
        user_agent="nikto/2.1",
        request_count=100,
        payload_indicators=["sql-like", "rce-indicator"],
    )
    result = calculate_risk(req)
    assert result.score >= 80
    assert result.level == RiskLevel.CRITICAL


def test_score_clamped_to_100():
    req = _make_request(
        path="/.env",
        user_agent="sqlmap/1.7",
        request_count=200,
        payload_indicators=["sql-like", "rce-indicator", "path-traversal", "xss"],
    )
    result = calculate_risk(req)
    assert result.score <= 100
