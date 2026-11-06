"""Extract defensive risk labels from request paths, queries, and payloads.

Every pattern is bounded (no nested unbounded quantifiers) so inspection time
grows linearly with input size.
"""

from __future__ import annotations

import re

from app.services.payload_normalization import (
    normalize_for_inspection,
    percent_decode_layers,
)

# Separators that start a new shell command. A single "&" is deliberately
# absent: it separates query-string parameters. The trailing whitespace is
# bounded and excludes line breaks: "[\r\n]\s*" is quadratic on a newline flood.
_SHELL_SEPARATOR = r"(?:;|\|\|?|&&|`|\$\(|[\r\n])[ \t]{0,16}"
# Whitespace, "(" or an SQL line comment between keywords: "union--x\nselect".
_SQL_GAP = r"(?:[\s(]|--[^\n]{0,100}\n|#[^\n]{0,100}\n){1,20}"

_HIGH_RISK_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "sql-like": tuple(
        re.compile(pattern)
        for pattern in (
            rf"\bunion{_SQL_GAP}(?:(?:all|distinct){_SQL_GAP})?select\b",
            # Quoted tautology: ' or 1=1, 'or'a'='a, '||1=1 (not prose like 'a' or b > c).
            r"['\"]\s*(?:or|and|\|\|)\s*(['\"]?)(\w{1,40})\1\s*(?:=|\blike\b)\s*['\"]?\2\b",
            r"\b(?:or|and)\s+(\d{1,10})\s*=\s*\1\b",
            r";\s*(?:drop|delete|insert|update|truncate|alter|exec(?:ute)?|shutdown|create|declare)\b",
            r"\b(?:drop|truncate)\s+table\s+(?:if\s+exists\s+)?[\w`\"\[\].]{1,64}\s*(?:;|--|#|\)|$)",
            # A numeric argument: "sleep(5)", "sleep(5-0)", not prose like "sleep (8 hours)".
            r"\b(?:sleep|pg_sleep)\s*\(\s*[\d\s+\-*/.]{1,20}\)",
            r"\bbenchmark\s*\(\s*\d+\s*,",
            r"\bwaitfor\s+delay\b",
            r"'\s*(?:--|#)",
            r"\binformation_schema\b",
            r"\bxp_cmdshell\b",
            r"\b(?:load_file|extractvalue|updatexml)\s*\(",
            r"\binto\s+(?:out|dump)file\b",
        )
    ),
    "xss": tuple(
        re.compile(pattern)
        for pattern in (
            r"<\s*script\b",
            # A URL scheme, tolerating control characters browsers strip
            # (java\tscript:), but not prose such as "JavaScript: the basics".
            r"\bjava[\s\x00-\x1f]{0,10}script\s*:(?:\S|\s*[\w$.]+\s*\()",
            r"\bdata\s*:\s*text/html\b",
            r"\bon(?:error|load|mouseover|mouseout|focus|blur|click|dblclick|toggle|begin"
            r"|animationstart|pointerover|keydown|keyup|input|change|submit)\s*=",
            # Any event handler attribute inside a tag: <div onpointerenter=...>.
            r"<[a-z][^>]{0,200}?\son[a-z]{3,25}\s*=",
            r"\bsrcdoc\s*=",
            r"\bdocument\s*\.\s*(?:cookie|domain)\b",
        )
    ),
    "path-traversal": tuple(
        re.compile(pattern)
        for pattern in (
            # Climbing two or more levels; a single "../guide.md" is an ordinary link.
            r"(?:\.\.[/\\]){2,}",
            r"\.\.;/",
            r"\.\.[/\\](?:etc|proc|windows|winnt|root|var|usr|home|web-inf|\.env|\.git)\b",
            r"/etc/(?:passwd|shadow)\b",
            r"/proc/self/",
            r"\b(?:boot|win)\.ini\b",
            r"c:\\windows\\",
        )
    ),
    "rce-indicator": tuple(
        re.compile(pattern)
        for pattern in (
            # Log4Shell, including ${${lower:j}ndi:...} and ${${::-j}...} obfuscation.
            r"\$\{[^}]{0,80}?(?:jndi|lower:|upper:|::-|env:|sys:)",
            r"\$\{ifs\}",
            r"/bin/(?:ba|z|k|da)?sh\b",
            r"\bcmd(?:\.exe)?\s+/c\b",
            r"\bpowershell\b.{0,40}?\s-(?:e|enc|encodedcommand)\b",
            # Glob-obfuscated paths: /???/c?t
            r"/\w{0,10}\?[\w?]{0,10}/\w{0,10}\?",
            # Commands needing a path, flag or file argument ("; cat flag.txt"),
            # so prose like "dog; cat lovers" does not match.
            _SHELL_SEPARATOR
            + r"(?:cat|ls|rm|chmod|cp|mv|tail|head|more|less)(?:\s+|\$\{ifs\})"
            r"(?:[-/~.$]|[\w-]{1,64}\.\w{1,5}\b)",
            # Argument-less recon commands at the end or before another separator
            # (a markdown table "| id | name |" is not a command).
            _SHELL_SEPARATOR
            + r"(?:whoami|id|uname|hostname|pwd|ifconfig|ipconfig)\b(?=\s*(?:$|[-;&`)]))",
            _SHELL_SEPARATOR
            + r"(?:wget|curl|nc|ncat|ping|nslookup|telnet)\s+"
            r"(?:-|https?:|\d|/|[\w-]{1,63}\.[a-z]{2,24}\b)",
            _SHELL_SEPARATOR + r"(?:bash|sh|zsh|python3?|perl|php|ruby)\s+(?:-|/)",
            r"\|\s*(?:ba|z)?sh\b",
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

# Only response headers an attacker gains from CRLF injection; ordinary form
# text such as "Re: yesterday" or "https://..." after a line break is not one.
_INJECTED_HEADER = re.compile(
    r"(?:^|[\r\n])[ \t]{0,8}(?:set-cookie|location|refresh|link|cache-control"
    r"|content-(?:type|length|disposition|security-policy)|www-authenticate"
    r"|access-control-[a-z-]{1,40}|x-[a-z0-9-]{1,40})[ \t]{0,8}:"
)
_ENCODED_LINE_BREAK = re.compile(r"%0[ad]", re.IGNORECASE)
# Encoded NULs only: a literal NUL byte is normal in binary uploads.
_ENCODED_NULL = re.compile(r"%00|\\u0000|&#0+;|&#x0+;", re.IGNORECASE)


def build_payload_excerpt(query: str, body: str, *, limit: int = 4096) -> str:
    """Combine bounded request query and body text for defensive inspection."""
    return "\n".join(value for value in (query, body) if value)[:limit]


def _part_indicators(raw: str) -> set[str]:
    if not raw:
        return set()
    normalized = normalize_for_inspection(raw)
    texts = (normalized.text,)
    if normalized.joined_text != normalized.text:
        texts += (normalized.joined_text,)
    found = {
        label
        for label, patterns in _HIGH_RISK_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns for text in texts)
    }
    layers = percent_decode_layers(raw)
    encoded_layers = layers[:-1] or [raw]
    if any(_ENCODED_LINE_BREAK.search(layer) for layer in encoded_layers) and (
        _INJECTED_HEADER.search(normalized.text)
    ):
        found.add("header-injection")
    if any(_ENCODED_NULL.search(layer) for layer in layers):
        found.add("null-byte")
    if normalized.decode_layers >= 2 or _COMMENT_INSIDE_WORD.search(layers[-1]):
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
    """Return sorted, unique labels for attack signatures in any common encoding.

    The whole body is inspected; callers bound its size (the proxy rejects
    bodies above ``PROXY_MAX_BODY_BYTES``).
    """
    body_text = body.decode("utf-8", errors="ignore")
    indicators: set[str] = set()
    for part in (path, query, body_text):
        indicators |= _part_indicators(part)
    if len(body) > LARGE_PAYLOAD_BYTES:
        indicators.add("large-payload")
    if body and content_type and _is_unusual_content_type(content_type):
        indicators.add("unusual-content-type")
    return sorted(indicators)
