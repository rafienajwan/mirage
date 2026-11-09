"""Who labeled events and changed cases, and the audit trail of operator actions."""

import dataclasses
from types import SimpleNamespace

import pytest

from app.api.routes import dashboard as dashboard_routes
from app.core import config
from app.schemas.dashboard import TrainingDataSummary
from app.schemas.event import AnalystLabel
from app.schemas.retraining import RetrainingArtifactReview, RetrainingRun
from app.services import honeytoken
from app.services import operators as operator_service
from app.storage import store
from tests.test_operator_auth import HEADERS, KEY, _as


@pytest.fixture
def production(monkeypatch):
    settings = dataclasses.replace(
        config.settings, app_env="production", api_key=KEY
    )
    monkeypatch.setattr(config, "settings", settings)


@pytest.fixture
async def alice(production):
    return await operator_service.create_operator("alice", "long enough pw", "analyst")


async def _audit_rows():
    return list(reversed(await store.get_audit(100)))


async def _make_event(client) -> str:
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "10.10.40.10",
            "method": "GET",
            "path": "/.env",
            "user_agent": "curl/8",
            "request_count": 90,
            "payload_indicators": ["path-traversal"],
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    return (await store.get_recent_events(limit=1))[0].event_id


async def _make_case(client, monkeypatch) -> str:
    monkeypatch.setattr(
        honeytoken,
        "settings",
        SimpleNamespace(
            decoy_login_token="mirage-login-canary",
            decoy_oauth_token="mirage-oauth-canary",
            decoy_service_token="mirage-service-canary",
            decoy_database_url="postgresql://decoy.invalid/mirage",
        ),
    )
    response = await client.post(
        "/api/v1/inspect",
        json={
            "ip_address": "10.10.40.10",
            "method": "GET",
            "path": "/.env",
            "user_agent": "curl/8",
            "request_count": 90,
            "payload_indicators": ["path-traversal"],
            "payload_excerpt": "SERVICE_TOKEN=mirage-service-canary",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    cases = await client.get("/api/v1/dashboard/actor-cases", headers=HEADERS)
    return cases.json()["cases"][0]["case_id"]


async def test_label_sets_labeled_by_and_audits(client, alice):
    event_id = await _make_event(client)
    response = await client.patch(
        f"/api/v1/dashboard/events/{event_id}/label",
        json={"label": "suspicious"},
        headers=_as("alice"),
    )
    assert response.status_code == 200
    assert response.json()["labeled_by"] == "alice"
    rows = await _audit_rows()
    assert [(r.operator, r.action, r.target, r.detail) for r in rows] == [
        ("alice", "label_event", event_id, "suspicious")
    ]


async def test_label_missing_event_writes_no_audit(client, alice):
    response = await client.patch(
        "/api/v1/dashboard/events/nope/label",
        json={"label": "normal"},
        headers=_as("alice"),
    )
    assert response.status_code == 404
    assert await _audit_rows() == []


async def test_case_open_and_update_record_author(client, alice, monkeypatch):
    case_id = await _make_case(client, monkeypatch)
    opened = await client.post(
        f"/api/v1/dashboard/actor-cases/{case_id}/open",
        json={"note": "triage", "assigned_to": "Alice"},
        headers=_as("alice"),
    )
    assert opened.status_code == 200
    assert opened.json()["updated_by"] == "alice"
    assert opened.json()["assigned_to"] == "alice"
    updated = await client.patch(
        f"/api/v1/dashboard/actor-case-workflows/{case_id}",
        json={"status": "investigating"},
        headers=_as("alice"),
    )
    assert updated.status_code == 200
    assert updated.json()["updated_by"] == "alice"
    rows = await _audit_rows()
    assert [(r.operator, r.action, r.target, r.detail) for r in rows] == [
        ("alice", "case_open", case_id, "open"),
        ("alice", "case_update", case_id, "investigating"),
    ]


async def test_unknown_assignee_is_422(client, alice, monkeypatch):
    case_id = await _make_case(client, monkeypatch)
    url = f"/api/v1/dashboard/actor-cases/{case_id}/open"
    bad = await client.post(
        url, json={"assigned_to": "nobody"}, headers=_as("alice")
    )
    assert bad.status_code == 422
    assert bad.json()["detail"] == "Unknown assignee"
    assert await _audit_rows() == []
    ok = await client.post(url, json={"assigned_to": ""}, headers=_as("alice"))
    assert ok.status_code == 200


async def test_retrain_and_revoke_audit_admin(client, production, monkeypatch):
    failing = await client.post(
        "/api/v1/dashboard/training-data/retrain", headers=HEADERS
    )
    assert failing.status_code == 409
    assert await _audit_rows() == []

    async def fake_train(limit):
        return RetrainingRun(
            artifact_path="models/candidate-1.joblib",
            artifact_sha256="0" * 64,
            training_summary=TrainingDataSummary(
                labeled_rows=0,
                exportable_rows=0,
                minimum_rows=1,
                minimum_rows_per_class=1,
                normal_rows=0,
                suspicious_rows=0,
                has_both_classes=False,
                has_minimum_class_rows=False,
                ready_for_training=False,
                analyst_labels={},
            ),
            metrics={},
            review=RetrainingArtifactReview(
                artifact_path="candidate-1.joblib",
                artifact_version=1,
                shadow_ready=True,
                metrics={},
                blockers=[],
                warnings=[],
            ),
        )

    monkeypatch.setattr(dashboard_routes, "train_from_labeled_events", fake_train)
    ok = await client.post("/api/v1/dashboard/training-data/retrain", headers=HEADERS)
    assert ok.status_code == 200

    decoy = await client.post(
        "/api/v1/decoy/respond",
        json={
            "path": "/api/config/settings",
            "decoy_type": "auto",
            "actor_hint": "actor-config",
            "risk_score": 80,
        },
        headers=HEADERS,
    )
    assert decoy.status_code == 200
    listed = await client.get(
        "/api/v1/dashboard/canary-assignments", headers=HEADERS
    )
    assignment_id = listed.json()["assignments"][0]["assignment_id"]
    missing = await client.post(
        "/api/v1/dashboard/canary-assignments/nope/revoke",
        json={"reason": "r"},
        headers=HEADERS,
    )
    assert missing.status_code == 404
    revoked = await client.post(
        f"/api/v1/dashboard/canary-assignments/{assignment_id}/revoke",
        json={"reason": "r"},
        headers=HEADERS,
    )
    assert revoked.status_code == 200

    rows = await _audit_rows()
    actions = [(r.operator, r.action, r.target) for r in rows]
    assert actions == [
        ("api-key", "retrain", "candidate-1.joblib"),
        ("api-key", "canary_revoke", assignment_id),
    ]


async def test_label_without_author_still_exports(client):
    event_id = await _make_event(client)
    await store.update_event_label(event_id, AnalystLabel.SUSPICIOUS, labeled_by=None)
    response = await client.get("/api/v1/dashboard/training-data/export")
    assert response.status_code == 200
    assert len(response.text.strip().splitlines()) == 1
