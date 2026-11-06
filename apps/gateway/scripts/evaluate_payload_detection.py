"""Measure payload detection and heuristic routing on a local CSIC 2010 copy.

Every request is scored as if sent by a browser at a low request rate, so the
result reflects payload signals alone, not user-agent or rate heuristics.

Usage (from apps/gateway):
    python scripts/evaluate_payload_detection.py --csic-dir data/csic-2010
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
import sys

gateway_dir = Path(__file__).resolve().parent.parent
if str(gateway_dir) not in sys.path:
    sys.path.insert(0, str(gateway_dir))

from app.ml.csic_http import CSICHTTPRequest, load_csic_http_directory  # noqa: E402
from app.schemas.request import InspectRequest  # noqa: E402
from app.services.decision_engine import make_decision  # noqa: E402
from app.services.payload_signals import detect_payload_indicators  # noqa: E402
from app.services.risk_engine import calculate_risk  # noqa: E402

BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
DECISIONS = ("redirect_to_decoy", "monitor", "allow")


def evaluate(records: Iterable[CSICHTTPRequest]) -> dict[str, dict[str, float]]:
    """Return per-class shares: flagged (any indicator) and each routing decision."""
    counts: dict[str, Counter[str]] = {"attack": Counter(), "normal": Counter()}
    for record in records:
        indicators = detect_payload_indicators(record.path, record.query, record.body)
        request = InspectRequest(
            ip_address="10.0.0.1",
            method=record.method,
            path=record.path[:2048] or "/",
            user_agent=BROWSER_USER_AGENT,
            request_count=1,
            payload_indicators=indicators,
        )
        decision = make_decision(
            calculate_risk(request), "", False, routing_mode="heuristic"
        )
        bucket = counts["attack" if record.label == 1 else "normal"]
        bucket["total"] += 1
        bucket["flagged"] += bool(indicators)
        bucket[decision.value] += 1
    return {
        name: {
            key: (bucket[key] / bucket["total"] if bucket["total"] else 0.0)
            for key in ("flagged", *DECISIONS)
        }
        for name, bucket in counts.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csic-dir", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(load_csic_http_directory(args.csic_dir).records)
    for name, shares in result.items():
        summary = "  ".join(f"{key}={value:.1%}" for key, value in shares.items())
        print(f"{name:6} {summary}")


if __name__ == "__main__":
    main()
