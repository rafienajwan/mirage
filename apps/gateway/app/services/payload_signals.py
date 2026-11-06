"""Extract defensive risk labels from request paths, queries, and payloads."""

from __future__ import annotations

import re

from app.services.payload_normalization import (
    normalize_for_inspection,
    percent_decode_layers,
)

BODY_INSPECTION_CHARS = 65_536

# Separators that start a new shell command. A single "&" is deliberately
# absent: it separates query-string parameters.
_SHELL_SEPARATOR = r"(?:;|\|\|?|&&|`|\$\()\s*"

_HIGH_RISK_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "sql-like": tuple(
        re.compile(pattern)
        for pattern in (
            r"\bunion\s+(?:all\s+)?select\b",
            r"['\"]\s*(?:or|and)\s+['\"]?\w+['\"]?\s*(?:=|<|>|\blike\b)",
            r"\b(?:or|and)\s+(\d+)\s*=\s*\1\b",
            r";\s*(?:drop|delete|insert|update|truncate|alter|exec(?:ute)?|shutdown|create|declare)\b",
            r"\b(?:drop|truncate)\s+table\b",
            # A bare numeric argument: "sleep(5)", not prose like "sleep (8 hours)".
            r"\b(?:sleep|pg_sleep)\s*\(\s*\d+(?:\.\d+)?\s*\)",
            r"\bbenchmark\s*\(\s*\d+\s*,",
            r"\bwaitfor\s+delay\b",
            r"'\s*(?:--|#|;)",
            r"\binformation_schema\b",
            r"\bxp_cmdshell\b",
            r"\bload_file\s*\(",
            r"\binto\s+(?:out|dump)file\b",
        )
    ),
    "xss": tuple(
        re.compile(pattern)
        for pattern in (
            r"<\s*script\b",
            # "javascript:" as a URL scheme, not prose such as "JavaScript: the basics".
            r"\bjavascript\s*:(?:\S|\s*[\w$.]+\s*\()",
            r"\bon(?:error|load|mouseover|mouseout|focus|blur|click|dblclick|toggle|begin"
            r"|animationstart|pointerover|keydown|keyup|input|change|submit)\s*=",
            r"<\s*(?:iframe|svg|object|embed)\b",
            r"\bdocument\s*\.\s*(?:cookie|domain)\b",
        )
    ),
    "path-traversal": tuple(
        re.compile(pattern)
        for pattern in (
            r"\.\.[/\\]",
            r"/etc/(?:passwd|shadow)\b",
            r"\b(?:boot|win)\.ini\b",
            r"c:\\windows\\",
        )
    ),
    "rce-indicator": tuple(
        re.compile(pattern)
        for pattern in (
            r"\$\{jndi:",
            r"/bin/(?:ba|z|k|da)?sh\b",
            r"\bcmd(?:\.exe)?\s+/c\b",
            r"\bpowershell\b.{0,40}?\s-(?:e|enc|encodedcommand)\b",
            # Commands that need a path or flag argument ("; cat /etc/hosts"),
            # so prose like "dog; cat lovers" does not match.
            _SHELL_SEPARATOR + r"(?:cat|ls|rm|chmod|cp|mv|tail|head)\s+[-/~.]",
            # Argument-less recon commands, followed by nothing or another separator.
            _SHELL_SEPARATOR
            + r"(?:whoami|id|uname|hostname|pwd|ifconfig|ipconfig)\b(?=\s*(?:$|[-;|&`)]))",
            _SHELL_SEPARATOR
            + r"(?:wget|curl|nc|ncat|ping|bash|sh|python|perl|nslookup)\s+(?:-|https?:|\d|/)",
        )
    ),
}

LARGE_PAYLOAD_BYTES = 65_536
_ALLOWED_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
        "application/xml",
        "text/xml",
    }
)
# An SQL inline comment splitting one word ("un/**/ion") is obfuscation.
_COMMENT_INSIDE_WORD = re.compile(r"\w/\*.{0,200}?\*/\w", re.DOTALL)

_HEADER_LINE = re.compile(r"[\r\n]\s*[a-z0-9-]{1,40}\s*:")
_ENCODED_LINE_BREAK = re.compile(r"%0[ad]", re.IGNORECASE)
_ENCODED_NULL = re.compile(r"%00")


def build_payload_excerpt(query: str, body: str, *, limit: int = 4096) -> str:
    """Combine bounded request query and body text for defensive inspection."""
    return "\n".join(value for value in (query, body) if value)[:limit]


def _part_indicators(raw: str) -> set[str]:
    if not raw:
        return set()
    normalized = normalize_for_inspection(raw)
    text = normalized.text
    found = {
        label
        for label, patterns in _HIGH_RISK_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    }
    # Inspect every encoded layer except the fully decoded one: an encoded
    # line break or NUL is an injection attempt, a literal one is not.
    encoded_layers = percent_decode_layers(raw)[:-1] or [raw]
    if any(_ENCODED_LINE_BREAK.search(layer) for layer in encoded_layers) and _HEADER_LINE.search(
        text
    ):
        found.add("header-injection")
    if "\x00" in text or any(_ENCODED_NULL.search(layer) for layer in encoded_layers):
        found.add("null-byte")
    if normalized.decode_layers >= 2 or _COMMENT_INSIDE_WORD.search(raw):
        found.add("encoded")
    return found


def _is_unusual_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type.startswith("application/") and media_type.endswith("+json"):
        return False
    return media_type not in _ALLOWED_MEDIA_TYPES


def detect_payload_indicators(
    path: str,
    query: str,
    body: bytes,
    *,
    content_type: str | None = None,
) -> list[str]:
    """Return sorted, unique labels for attack signatures in any common encoding."""
    body_text = body.decode("utf-8", errors="ignore")[:BODY_INSPECTION_CHARS]
    indicators: set[str] = set()
    for part in (path, query, body_text):
        indicators |= _part_indicators(part)
    if len(body) > LARGE_PAYLOAD_BYTES:
        indicators.add("large-payload")
    if body and content_type and _is_unusual_content_type(content_type):
        indicators.add("unusual-content-type")
    return sorted(indicators)
