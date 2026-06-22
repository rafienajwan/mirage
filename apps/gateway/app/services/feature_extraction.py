"""Stable request-to-feature transformation for heuristic and ML scoring."""

from __future__ import annotations

import math

from app.schemas.request import InspectRequest
from app.services.risk_engine import (
    HIGH_RISK_INDICATORS,
    MEDIUM_RISK_INDICATORS,
    SENSITIVE_PATHS,
    SUSPICIOUS_UA_KEYWORDS,
)

FeatureVector = dict[str, float]

FEATURE_NAMES = (
    "request_count_log",
    "path_length",
    "path_depth",
    "sensitive_path",
    "suspicious_user_agent",
    "high_risk_indicator_count",
    "medium_risk_indicator_count",
    "method_get",
    "method_post",
    "method_write",
    "flow_duration_ms",
    "flow_packets_per_second",
    "packet_length_mean",
    "syn_flag_count",
    "destination_port",
    "average_packet_size",
)


def extract_features(request: InspectRequest) -> FeatureVector:
    """Convert request metadata into a numeric, model-ready feature vector."""
    path = request.path.lower()
    user_agent = request.user_agent.lower()
    indicators = {indicator.lower() for indicator in request.payload_indicators}
    method = request.method.upper()

    return {
        "request_count_log": round(math.log1p(request.request_count), 6),
        "path_length": float(len(request.path)),
        "path_depth": float(len([part for part in request.path.split("/") if part])),
        "sensitive_path": float(any(item in path for item in SENSITIVE_PATHS)),
        "suspicious_user_agent": float(
            any(item in user_agent for item in SUSPICIOUS_UA_KEYWORDS)
        ),
        "high_risk_indicator_count": float(len(indicators & HIGH_RISK_INDICATORS)),
        "medium_risk_indicator_count": float(
            len(indicators & MEDIUM_RISK_INDICATORS)
        ),
        "method_get": float(method == "GET"),
        "method_post": float(method == "POST"),
        "method_write": float(method in {"POST", "PUT", "PATCH", "DELETE"}),
        "flow_duration_ms": float(request.flow_duration_ms or 0.0),
        "flow_packets_per_second": float(request.flow_packets_per_second or 0.0),
        "packet_length_mean": float(request.packet_length_mean or 0.0),
        "syn_flag_count": float(request.syn_flag_count or 0),
        "destination_port": float(request.destination_port or 0),
        "average_packet_size": float(request.average_packet_size or 0.0),
    }
