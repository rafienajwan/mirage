import pytest

from app.core.passwords import hash_password, validate_password, verify_password


def test_round_trip():
    assert verify_password("correct horse 1", hash_password("correct horse 1"))


def test_wrong_password():
    assert not verify_password("wrong password!", hash_password("correct horse 1"))


def test_salted():
    assert hash_password("same password!") != hash_password("same password!")


def test_format():
    assert hash_password("x" * 12).startswith("scrypt$16384$8$1$")


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "scrypt$",
        "bcrypt$1$2$3$a$b",
        "scrypt$16384$8$1$!!$!!",
        "scrypt$x$8$1$AA$AA",
        "scrypt$1048576$8$1$AA$AA",
    ],
)
def test_malformed_hash_is_false(encoded):
    assert verify_password("anything goes", encoded) is False


@pytest.mark.parametrize("password", ["x" * 11, "x" * 257])
def test_length_bounds(password):
    with pytest.raises(ValueError):
        validate_password(password)


def test_bounds_accept():
    validate_password("x" * 12)
    validate_password("x" * 256)


def test_dummy_hash_is_valid_but_never_matches():
    from app.core.passwords import DUMMY_HASH

    assert DUMMY_HASH.startswith("scrypt$")
    assert verify_password("anything goes", DUMMY_HASH) is False
