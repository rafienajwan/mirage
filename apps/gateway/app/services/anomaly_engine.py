"""Anomaly detection engine — lightweight heuristic placeholder.

This module provides a clean interface for anomaly detection. The current
implementation uses simple heuristics. A real ML model can be plugged in later
by implementing the ``AnomalyEngine`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.request import InspectRequest


@dataclass
class AnomalyResult:
    """Output of the anomaly detection engine."""

    is_anomalous: bool
    confidence: float  # 0.0–1.0
    signals: list[str] = field(default_factory=list)


class AnomalyDetector(Protocol):
    """Interface for pluggable anomaly detectors."""

    def detect(self, request: InspectRequest) -> AnomalyResult: ...


class HeuristicAnomalyDetector:
    """Simple rule-based anomaly detector for the MVP phase."""

    def detect(self, request: InspectRequest) -> AnomalyResult:
        signals: list[str] = []

        # High request frequency
        if request.request_count >= 50:
            signals.append("Unusually high request frequency")

        # Sensitive route access
        sensitive_patterns = ["/.env", "/admin", "/config", "/internal", "/.git"]
        for pattern in sensitive_patterns:
            if pattern in request.path.lower():
                signals.append(f"Sensitive route access: {request.path}")
                break

        # Abnormal user-agent
        ua_lower = request.user_agent.lower()
        suspicious_tools = ["sqlmap", "nikto", "nmap", "dirbuster", "burpsuite"]
        for tool in suspicious_tools:
            if tool in ua_lower:
                signals.append(f"Abnormal user-agent: {tool}")
                break

        # Repeated suspicious pattern (multiple payload indicators)
        if len(request.payload_indicators) >= 2:
            signals.append("Multiple suspicious payload indicators")

        confidence = min(len(signals) * 0.25, 1.0)
        is_anomalous = len(signals) > 0

        return AnomalyResult(
            is_anomalous=is_anomalous,
            confidence=round(confidence, 2),
            signals=signals,
        )


# Default detector instance
anomaly_detector: AnomalyDetector = HeuristicAnomalyDetector()
