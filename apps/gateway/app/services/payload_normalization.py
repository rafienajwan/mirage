"""Canonicalize request text so attack signatures match in any common encoding."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
import unicodedata
from urllib.parse import unquote, unquote_plus

MAX_DECODE_ROUNDS = 3

_JSON_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_JSON_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|[\"\\/bfnrt])")
# MySQL executes the body of a versioned comment: /*!50000union*/ means "union".
_SQL_VERSIONED_COMMENT = re.compile(r"/\*!\d{0,6}(.{0,200}?)\*/", re.DOTALL)
# A comment splitting one word (un/**/ion) joins it; elsewhere it is a separator.
_SQL_COMMENT_INSIDE_WORD = re.compile(r"(?<=\w)/\*.{0,200}?\*/(?=\w)", re.DOTALL)
_SQL_INLINE_COMMENT = re.compile(r"/\*.{0,200}?\*/", re.DOTALL)
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\r\n]+")


@dataclass(frozen=True)
class NormalizedPayload:
    """Normalized, lowercased text and how many percent-decoding rounds changed it.

    ``text`` reads SQL inline comments as whitespace (how databases parse
    ``UNION/**/SELECT``); ``joined_text`` deletes them (how naive filters turn
    ``UN/**/ION`` into ``UNION``). Signatures are matched against both.
    """

    text: str
    decode_layers: int
    joined_text: str = ""


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


def _decode_json_escape(match: re.Match[str]) -> str:
    token = match.group(1)
    if token.startswith("u"):
        return chr(int(token[1:], 16))
    return _JSON_ESCAPES[token]


def normalize_for_inspection(raw: str) -> NormalizedPayload:
    """Decode, fold, and lowercase text for signature matching. Never raises."""
    layers = percent_decode_layers(raw)
    text = _JSON_ESCAPE.sub(_decode_json_escape, layers[-1])
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    # NULs are reported separately; removing them defeats s\x00elect-style
    # splitting and UTF-16 interleaving.
    text = text.replace("\x00", "")
    text = _SQL_VERSIONED_COMMENT.sub(r" \1 ", text)
    joined = _SQL_INLINE_COMMENT.sub(" ", _SQL_COMMENT_INSIDE_WORD.sub("", text))
    text = _SQL_INLINE_COMMENT.sub(" ", text)
    return NormalizedPayload(
        text=_HORIZONTAL_WHITESPACE.sub(" ", text).lower(),
        decode_layers=len(layers) - 1,
        joined_text=_HORIZONTAL_WHITESPACE.sub(" ", joined).lower(),
    )
