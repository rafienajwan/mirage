"""Extract defensive risk labels from request paths, queries, and payloads."""

from __future__ import annotations


def build_payload_excerpt(query: str, body: str, *, limit: int = 4096) -> str:
    """Combine bounded request query and body text for defensive inspection."""
    return "\n".join(value for value in (query, body) if value)[:limit]


def detect_payload_indicators(path: str, query: str, body: bytes) -> list[str]:
    """Return stable labels for common malicious request signatures."""
    body_text = body.decode("utf-8", errors="ignore")[:65_536]
    sample = f"{path}?{query}\n{body_text}".lower()
    indicators: list[str] = []

    if any(
        token in sample
        for token in ("union select", "' or 1=1", '" or 1=1', "drop table", "sleep(")
    ):
        indicators.append("sql-like")
    if any(token in sample for token in ("../", "..\\", "%2e%2e")):
        indicators.append("path-traversal")
    if any(token in sample for token in ("<script", "javascript:", "onerror=")):
        indicators.append("xss")
    if any(token in sample for token in ("${jndi:", "/bin/sh", "cmd.exe /c", "powershell -enc")):
        indicators.append("rce-indicator")

    return indicators
