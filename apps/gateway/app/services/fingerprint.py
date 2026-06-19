"""Threat fingerprinting service.

Generates privacy-safe hashes from request metadata. Does NOT store raw
identifiers. Uses SHA-256 with a salt for one-way hashing.
"""

from __future__ import annotations

import hashlib

_FINGERPRINT_SALT = "mirage_demo_salt_v1"


def _categorize_path(path: str) -> str:
    """Map a path to a coarse category for fingerprinting."""
    path_lower = path.lower()
    if "/admin" in path_lower:
        return "admin"
    if "/.env" in path_lower or "/config" in path_lower or "/secret" in path_lower:
        return "config"
    if "/.git" in path_lower:
        return "scm"
    if "/api/" in path_lower:
        return "api"
    return "general"


def generate_fingerprint(
    ip_address: str,
    user_agent: str,
    path: str,
    payload_indicators: list[str],
) -> str:
    """Generate a privacy-safe SHA-256 fingerprint hash.

    The hash is derived from:
    - IP address
    - User-Agent
    - Path category (not raw path)
    - Sorted payload indicator labels

    Raw identifiers are not stored.
    """
    path_category = _categorize_path(path)
    indicators_str = ",".join(sorted(i.lower() for i in payload_indicators))
    raw = f"{ip_address}|{user_agent}|{path_category}|{indicators_str}|{_FINGERPRINT_SALT}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
