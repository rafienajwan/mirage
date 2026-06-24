"""Build labeled JSONL training rows from reviewed gateway events."""

from __future__ import annotations

import json
from typing import Iterable

from app.schemas.event import AnalystLabel, EventRecord


LABEL_TO_BINARY = {
    AnalystLabel.NORMAL: 0,
    AnalystLabel.FALSE_POSITIVE: 0,
    AnalystLabel.SUSPICIOUS: 1,
    AnalystLabel.FALSE_NEGATIVE: 1,
}


def event_to_training_row(event: EventRecord) -> dict | None:
    """Convert an analyst-labeled event into the trainer's JSONL row shape."""
    if event.analyst_label is None or not event.feature_vector:
        return None

    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat(),
        "label": LABEL_TO_BINARY[event.analyst_label],
        "analyst_label": event.analyst_label.value,
        "features": event.feature_vector,
    }


def events_to_jsonl(events: Iterable[EventRecord]) -> str:
    rows = [
        row
        for event in events
        if (row := event_to_training_row(event)) is not None
    ]
    return "".join(f"{json.dumps(row, sort_keys=True)}\n" for row in rows)
