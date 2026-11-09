"""Password hashing for operator accounts (scrypt, stdlib only)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets

_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
_MAX_N = 2**16
_MIN_LENGTH = 12
_MAX_LENGTH = 256


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=_DKLEN,
        maxmem=128 * n * r * 2 + (1 << 20),
    )


def hash_password(password: str) -> str:
    """Return a salted `scrypt$n$r$p$salt$digest` string (base64 fields)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _derive(password, salt, _N, _R, _P)
    return "scrypt${}${}${}${}${}".format(
        _N,
        _R,
        _P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against a stored hash; malformed input is simply False."""
    parts = encoded.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        # Cap the cost so a tampered row cannot exhaust memory.
        if not (1 < n <= _MAX_N) or n & (n - 1) or r < 1 or p < 1 or r > 32 or p > 16:
            return False
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
        actual = _derive(password, salt, n, r, p)
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(actual, expected)


def validate_password(password: str) -> None:
    """Raise ValueError unless the password length is within policy."""
    if not _MIN_LENGTH <= len(password) <= _MAX_LENGTH:
        raise ValueError(f"password must be {_MIN_LENGTH}-{_MAX_LENGTH} characters")


# A real hash of a random value, so unknown-user logins cost the same as real ones.
DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
