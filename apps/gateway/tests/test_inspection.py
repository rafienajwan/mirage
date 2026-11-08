"""Tests for the shared inspection workflow."""

import threading

from app.schemas.request import InspectRequest
from app.services import inspection


async def test_ml_shadow_scoring_runs_off_the_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    scorer_threads: list[int] = []

    def fake_score(features, *, heuristic_decision):
        scorer_threads.append(threading.get_ident())
        return None

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(inspection, "score_ml_shadow", fake_score)
    monkeypatch.setattr(inspection, "log_inspection", fake_log)

    await inspection.inspect_and_log(
        InspectRequest(ip_address="10.0.0.2", method="GET", path="/api/products")
    )

    assert len(scorer_threads) == 1
    assert scorer_threads[0] != loop_thread
