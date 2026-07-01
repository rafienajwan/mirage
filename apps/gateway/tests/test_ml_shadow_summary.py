"""Tests for ML shadow agreement summaries."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.decision import Decision
from app.schemas.event import EventRecord
from app.schemas.ml import MLShadowScore
from app.services.ml_shadow_summary import summarize_ml_shadow_events


def _event(
    event_id: str,
    decision: Decision,
    *,
    shadow_decision: Decision | None = None,
) -> EventRecord:
    shadow = None
    if shadow_decision is not None:
        shadow = MLShadowScore(
            artifact="risk_model.joblib",
            probability=0.8 if shadow_decision == Decision.REDIRECT_TO_DECOY else 0.2,
            score=80.0 if shadow_decision == Decision.REDIRECT_TO_DECOY else 20.0,
            prediction="suspicious"
            if shadow_decision == Decision.REDIRECT_TO_DECOY
            else "normal",
            shadow_decision=shadow_decision.value,
            agrees_with_decision=shadow_decision == decision,
        )
    return EventRecord(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc),
        ip_address="10.0.0.1",
        path="/api/users",
        method="GET",
        risk_score=70.0,
        decision=decision,
        summary="test event",
        ml_shadow=shadow,
    )


def test_summarize_ml_shadow_events_counts_agreement():
    summary = summarize_ml_shadow_events(
        [
            _event("evt-1", Decision.ALLOW, shadow_decision=Decision.ALLOW),
            _event(
                "evt-2",
                Decision.MONITOR,
                shadow_decision=Decision.REDIRECT_TO_DECOY,
            ),
            _event("evt-3", Decision.ALLOW),
        ]
    )

    assert summary.inspected_events == 3
    assert summary.shadow_events == 2
    assert summary.agreements == 1
    assert summary.disagreements == 1
    assert summary.agreement_rate == 0.5
    assert summary.live_decisions.allow == 1
    assert summary.live_decisions.monitor == 1
    assert summary.shadow_decisions.allow == 1
    assert summary.shadow_decisions.redirect_to_decoy == 1


@pytest.mark.asyncio
async def test_ml_shadow_summary_endpoint_returns_empty_summary(client):
    response = await client.get("/api/v1/dashboard/ml-shadow/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["inspected_events"] == 0
    assert body["shadow_events"] == 0
    assert body["agreement_rate"] == 0.0
