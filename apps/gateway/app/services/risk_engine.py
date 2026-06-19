"""Risk scoring engine — hybrid heuristic scorer.

Evaluates request metadata and returns a risk score (0–100) with human-readable
reasons. Designed to be explainable and extendable with ML later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.decision import RiskLevel
from app.schemas.request import InspectRequest

# ── Sensitive path patterns ────────────────────────────────────

SENSITIVE_PATHS = [
    "/admin",
    "/.env",
    "/config",
    "/internal",
    "/debug",
    "/secret",
    "/api/admin",
    "/api/config",
    "/api/internal",
    "/wp-admin",
    "/phpmyadmin",
    "/.git",
    "/backup",
]

# ── Suspicious user-agent keywords ─────────────────────────────

SUSPICIOUS_UA_KEYWORDS = [
    "sqlmap",
    "nikto",
    "nmap",
    "dirbuster",
    "gobuster",
    "burpsuite",
    "havij",
    "acunetix",
    "nessus",
    "zap",
    "wpscan",
    "masscan",
    "hydra",
    "curl",
    "wget",
    "python-requests",
    "go-http-client",
    "scrapy",
]

# ── Known payload indicator labels ─────────────────────────────

HIGH_RISK_INDICATORS = {"sql-like", "rce-indicator", "path-traversal", "xss"}
MEDIUM_RISK_INDICATORS = {"encoded", "unusual-content-type", "large-payload"}


@dataclass
class RiskResult:
    """Output of the risk scoring engine."""

    score: float  # 0–100
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)


def _score_path(path: str) -> tuple[float, list[str]]:
    """Score based on path sensitivity."""
    path_lower = path.lower()
    for sensitive in SENSITIVE_PATHS:
        if sensitive in path_lower:
            return 25.0, [f"Sensitive path access: {path}"]
    return 0.0, []


def _score_request_count(count: int) -> tuple[float, list[str]]:
    """Score based on request frequency."""
    if count >= 100:
        return 25.0, [f"Very high request count: {count}"]
    if count >= 50:
        return 15.0, [f"Elevated request count: {count}"]
    if count >= 20:
        return 8.0, [f"Moderate request count: {count}"]
    return 0.0, []


def _score_user_agent(ua: str) -> tuple[float, list[str]]:
    """Score based on suspicious user-agent keywords."""
    ua_lower = ua.lower()
    for keyword in SUSPICIOUS_UA_KEYWORDS:
        if keyword in ua_lower:
            return 15.0, [f"Suspicious user-agent keyword: {keyword}"]
    return 0.0, []


def _score_payload_indicators(indicators: list[str]) -> tuple[float, list[str]]:
    """Score based on payload indicator labels."""
    score = 0.0
    reasons: list[str] = []

    for indicator in indicators:
        ind_lower = indicator.lower()
        if ind_lower in HIGH_RISK_INDICATORS:
            score += 20.0
            reasons.append(f"High-risk payload indicator: {indicator}")
        elif ind_lower in MEDIUM_RISK_INDICATORS:
            score += 8.0
            reasons.append(f"Medium-risk payload indicator: {indicator}")

    return min(score, 40.0), reasons  # cap at 40


def calculate_risk(request: InspectRequest) -> RiskResult:
    """Calculate risk score for a simulated request.

    Returns a RiskResult with score 0–100, risk level, and reasons.
    """
    total = 0.0
    reasons: list[str] = []

    # 1. Path scoring
    path_score, path_reasons = _score_path(request.path)
    total += path_score
    reasons.extend(path_reasons)

    # 2. Request frequency
    count_score, count_reasons = _score_request_count(request.request_count)
    total += count_score
    reasons.extend(count_reasons)

    # 3. User-agent
    ua_score, ua_reasons = _score_user_agent(request.user_agent)
    total += ua_score
    reasons.extend(ua_reasons)

    # 4. Payload indicators
    payload_score, payload_reasons = _score_payload_indicators(
        request.payload_indicators
    )
    total += payload_score
    reasons.extend(payload_reasons)

    # Clamp to 0–100
    total = max(0.0, min(100.0, total))

    # Determine level
    if total < 30:
        level = RiskLevel.LOW
    elif total < 60:
        level = RiskLevel.MEDIUM
    elif total < 80:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.CRITICAL

    if not reasons:
        reasons.append("No suspicious indicators detected")

    return RiskResult(score=round(total, 1), level=level, reasons=reasons)
