"""Operator account management CLI."""

import asyncio
import io

import pytest

from app.services import operators as operator_service
from scripts import manage_operators


def run(argv, stdin_text=""):
    return manage_operators.main(argv, stdin=io.StringIO(stdin_text))


def create_alice():
    return run(
        ["create", "alice", "--role", "analyst", "--password-stdin"], "long enough pw\n"
    )


def authenticate(name, password):
    return asyncio.run(operator_service.authenticate(name, password))


def test_create_then_list(capsys):
    assert create_alice() == 0
    capsys.readouterr()
    assert run(["list"]) == 0
    assert "alice analyst enabled" in capsys.readouterr().out


def test_duplicate_is_an_error(capsys):
    assert create_alice() == 0
    capsys.readouterr()
    assert create_alice() == 1
    err = capsys.readouterr().err
    assert "Operator already exists" in err
    assert "Traceback" not in err


@pytest.mark.parametrize(
    ("name", "password"),
    [("api-key", "long enough pw"), ("Bad!", "long enough pw"), ("carol", "short")],
)
def test_invalid_input_is_an_error(name, password, capsys):
    code = run(["create", name, "--role", "analyst", "--password-stdin"], password + "\n")
    assert code == 1
    err = capsys.readouterr().err
    assert err.strip()
    assert "Traceback" not in err


def test_disable_and_enable():
    assert create_alice() == 0
    assert run(["disable", "alice"]) == 0
    assert authenticate("alice", "long enough pw") is None
    assert run(["enable", "alice"]) == 0
    assert authenticate("alice", "long enough pw") is not None


def test_reset_password_and_set_role():
    assert create_alice() == 0
    code = run(["reset-password", "alice", "--password-stdin"], "another long pw\n")
    assert code == 0
    assert authenticate("alice", "long enough pw") is None
    assert authenticate("alice", "another long pw") is not None
    assert run(["set-role", "alice", "admin"]) == 0
    assert authenticate("alice", "another long pw").role == "admin"


def test_unknown_operator_is_an_error(capsys):
    assert run(["disable", "ghost"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_password_not_accepted_from_argv():
    with pytest.raises(SystemExit) as exc:
        run(["create", "bob", "--role", "analyst", "--password", "secret123456"])
    assert exc.value.code == 2


def test_prompt_requires_matching_entries(monkeypatch, capsys):
    answers = iter(["long enough pw", "different pw here"])
    monkeypatch.setattr(manage_operators.getpass, "getpass", lambda *_: next(answers))
    assert run(["create", "bob", "--role", "analyst"]) == 1
    assert "match" in capsys.readouterr().err
