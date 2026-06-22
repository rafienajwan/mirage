"""Tests for decision logic and request inspection."""

import pytest

from app.schemas.decision import Decision, RiskLevel
from app.services.decision_engine import make_decision
from app.services.risk_engine import RiskResult


def test_allow_low_risk():
    risk = RiskResult(score=10.0, level=RiskLevel.LOW, reasons=["Normal"])
    decision = make_decision(risk, fingerprint_hash="abc123", is_anomalous=False)
    assert decision == Decision.ALLOW


def test_monitor_medium_risk():
    risk = RiskResult(score=45.0, level=RiskLevel.MEDIUM, reasons=["Elevated"])
    decision = make_decision(risk, fingerprint_hash="abc123", is_anomalous=True)
    assert decision == Decision.MONITOR


def test_redirect_high_risk():
    risk = RiskResult(score=70.0, level=RiskLevel.HIGH, reasons=["Suspicious"])
    decision = make_decision(risk, fingerprint_hash="abc123", is_anomalous=True)
    assert decision == Decision.REDIRECT_TO_DECOY


def test_redirect_critical_risk():
    risk = RiskResult(score=90.0, level=RiskLevel.CRITICAL, reasons=["Critical"])
    decision = make_decision(risk, fingerprint_hash="abc123", is_anomalous=True)
    assert decision == Decision.REDIRECT_TO_DECOY


def test_redirect_known_malicious_fingerprint():
    from app.services.decision_engine import register_malicious_fingerprint

    register_malicious_fingerprint("known_bad_hash")
    risk = RiskResult(score=5.0, level=RiskLevel.LOW, reasons=["Known bad"])
    decision = make_decision(
        risk, fingerprint_hash="known_bad_hash", is_anomalous=False
    )
    assert decision == Decision.REDIRECT_TO_DECOY


@pytest.mark.asyncio
async def test_inspect_endpoint_normal(client):
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "192.168.1.1",
            "method": "GET",
            "path": "/api/v1/products",
            "user_agent": "Mozilla/5.0",
            "request_count": 2,
            "payload_indicators": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "allow"
    assert data["risk_level"] == "low"


@pytest.mark.asyncio
async def test_inspect_endpoint_suspicious(client):
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "10.0.0.99",
            "method": "POST",
            "path": "/.env",
            "user_agent": "sqlmap/1.7",
            "request_count": 85,
            "payload_indicators": ["sql-like", "path-traversal"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "redirect_to_decoy"
    assert data["risk_level"] in ("high", "critical")


@pytest.mark.asyncio
async def test_inspect_rejects_unbounded_input(client):
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "192.168.1.1",
            "method": "GET",
            "path": "/" + "a" * 2050,
            "request_count": 1,
            "payload_indicators": [],
        },
    )
    assert response.status_code == 422
