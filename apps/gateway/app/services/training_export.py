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

MINIMUM_TRAINING_ROWS = 20
MINIMUM_TRAINING_ROWS_PER_CLASS = 2


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


def training_data_summary(
    events: Iterable[EventRecord],
    minimum_rows: int = MINIMUM_TRAINING_ROWS,
    minimum_rows_per_class: int = MINIMUM_TRAINING_ROWS_PER_CLASS,
) -> dict:
    """Summarize whether analyst labels are ready for a first training run."""
    analyst_labels = {label.value: 0 for label in AnalystLabel}
    normal_rows = 0
    suspicious_rows = 0
    labeled_rows = 0
    exportable_rows = 0

    for event in events:
        if event.analyst_label is None:
            continue

        labeled_rows += 1
        analyst_labels[event.analyst_label.value] += 1

        row = event_to_training_row(event)
        if row is None:
            continue

        exportable_rows += 1
        if row["label"] == 0:
            normal_rows += 1
        else:
            suspicious_rows += 1

    has_both_classes = normal_rows > 0 and suspicious_rows > 0
    has_minimum_class_rows = (
        normal_rows >= minimum_rows_per_class
        and suspicious_rows >= minimum_rows_per_class
    )
    ready_for_training = (
        exportable_rows >= minimum_rows
        and has_both_classes
        and has_minimum_class_rows
    )

    return {
        "labeled_rows": labeled_rows,
        "exportable_rows": exportable_rows,
        "minimum_rows": minimum_rows,
        "minimum_rows_per_class": minimum_rows_per_class,
        "normal_rows": normal_rows,
        "suspicious_rows": suspicious_rows,
        "has_both_classes": has_both_classes,
        "has_minimum_class_rows": has_minimum_class_rows,
        "ready_for_training": ready_for_training,
        "analyst_labels": analyst_labels,
    }
