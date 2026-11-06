"""Canonicalize request text so attack signatures match in any common encoding."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
import unicodedata
from urllib.parse import unquote, unquote_plus

MAX_DECODE_ROUNDS = 3

_JSON_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
_SQL_INLINE_COMMENT = re.compile(r"/\*.{0,200}?\*/", re.DOTALL)
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\r\n]+")


@dataclass(frozen=True)
class NormalizedPayload:
    """Normalized, lowercased text and how many percent-decoding rounds changed it."""

    text: str
    decode_layers: int


def percent_decode_layers(raw: str) -> list[str]:
    """Return the raw text followed by each percent-decoding round that changed it.

    Form encoding (``+`` as a space) applies only to the first round; later
    rounds decode ``%XX`` sequences only, so a literal ``+`` that was itself
    encoded (``%2B``) is not mistaken for another encoding layer.
    """
    layers = [raw]
    current = raw
    for round_index in range(MAX_DECODE_ROUNDS):
        decoder = unquote_plus if round_index == 0 else unquote
        decoded = decoder(current, errors="replace")
        if decoded == current:
            break
        layers.append(decoded)
        current = decoded
    return layers


def normalize_for_inspection(raw: str) -> NormalizedPayload:
    """Decode, fold, and lowercase text for signature matching. Never raises."""
    layers = percent_decode_layers(raw)
    text = layers[-1]
    text = _JSON_UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = _SQL_INLINE_COMMENT.sub(" ", text)
    text = _HORIZONTAL_WHITESPACE.sub(" ", text)
    return NormalizedPayload(text=text.lower(), decode_layers=len(layers) - 1)
