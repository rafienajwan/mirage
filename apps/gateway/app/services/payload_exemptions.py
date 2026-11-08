"""Per-route exemptions for payload detection labels.

Some routes legitimately accept attack-shaped content (code snippets, rich
text). ``PAYLOAD_EXEMPTIONS`` lists rules of the form
``METHOD PATH_GLOB:label[,label...]`` separated by ``;``. A rule removes its
labels from routing for matching requests; inspection still runs and the
removed labels are recorded on the event.

Rules apply only to canonical paths, so an exempt prefix cannot be used to
reach a different upstream route (``/api/posts/..%2fadmin``).
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import logging

from app.core import config
from app.services.risk_engine import HIGH_RISK_INDICATORS, MEDIUM_RISK_INDICATORS

logger = logging.getLogger(__name__)

KNOWN_LABELS = frozenset(HIGH_RISK_INDICATORS) | frozenset(MEDIUM_RISK_INDICATORS)


@dataclass(frozen=True)
class ExemptionRule:
    method: str
    path_glob: str
    labels: frozenset[str]

    def matches(self, method: str, path: str) -> bool:
        return self.method in {"*", method.upper()} and fnmatchcase(path, self.path_glob)


def parse_exemptions(raw: str) -> tuple[ExemptionRule, ...]:
    """Parse the setting; raise ValueError naming the rule number, not its text."""
    rules = []
    for index, text in enumerate((part.strip() for part in raw.split(";") if part.strip()), 1):
        head, separator, label_text = text.rpartition(":")
        parts = head.split()
        labels = frozenset(label.strip() for label in label_text.split(",") if label.strip())
        if (
            not separator
            or len(parts) != 2
            or not parts[1].startswith("/")
            or not labels
            or not labels <= KNOWN_LABELS
        ):
            raise ValueError(f"PAYLOAD_EXEMPTIONS rule {index} is invalid")
        rules.append(ExemptionRule(parts[0].upper(), parts[1], labels))
    return tuple(rules)


def is_canonical_path(path: str) -> bool:
    if any(token in path for token in ("%", "\\", ";", "//")):
        return False
    return not any(segment in {".", ".."} for segment in path.split("/"))


def _configured_rules() -> tuple[ExemptionRule, ...]:
    try:
        return parse_exemptions(config.settings.payload_exemptions)
    except ValueError as exc:
        # Production refuses to start with a bad setting; development logs it.
        logger.warning("Ignoring PAYLOAD_EXEMPTIONS: %s", exc)
        return ()


def apply_exemptions(
    method: str,
    path: str,
    indicators: list[str],
    rules: tuple[ExemptionRule, ...] | None = None,
) -> tuple[list[str], list[str]]:
    """Split indicators into (kept, exempted) for this request."""
    if rules is None:
        rules = _configured_rules()
    if not rules or not indicators or not is_canonical_path(path):
        return list(indicators), []
    exempt_labels: set[str] = set()
    for rule in rules:
        if rule.matches(method, path):
            exempt_labels |= rule.labels
    kept = [label for label in indicators if label not in exempt_labels]
    exempted = [label for label in indicators if label in exempt_labels]
    return kept, exempted
