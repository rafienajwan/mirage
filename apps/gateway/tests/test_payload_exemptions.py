"""Per-route payload detection exemptions."""

import dataclasses

import pytest

from app.core import config
from app.schemas.request import InspectRequest
from app.services.payload_exemptions import (
    ExemptionRule,
    apply_exemptions,
    is_canonical_path,
    parse_exemptions,
)
from app.services.risk_engine import calculate_risk


def test_parse_valid_rules():
    rules = parse_exemptions("POST /api/posts:xss;PUT /api/snippets/*:rce-indicator,sql-like")
    assert rules == (
        ExemptionRule("POST", "/api/posts", frozenset({"xss"})),
        ExemptionRule("PUT", "/api/snippets/*", frozenset({"rce-indicator", "sql-like"})),
    )


def test_parse_wildcard_method_and_empty():
    assert parse_exemptions("* /x:xss")[0].method == "*"
    assert parse_exemptions("") == ()
    assert parse_exemptions("  ;  ") == ()


@pytest.mark.parametrize("raw", ["POST /x:bogus", "POST:xss", "POST /x", "POST x:xss", ":xss"])
def test_parse_rejects_bad_rules(raw):
    with pytest.raises(ValueError) as exc:
        parse_exemptions(raw)
    assert "rule 1" in str(exc.value)


RULES = parse_exemptions("POST /api/posts:xss;PUT /api/snippets/*:rce-indicator")


def test_method_mismatch_exempts_nothing():
    assert apply_exemptions("GET", "/api/posts", ["xss"], RULES) == (["xss"], [])


def test_rule_method_is_case_insensitive():
    rules = parse_exemptions("post /api/posts:xss")
    assert apply_exemptions("POST", "/api/posts", ["xss"], rules) == ([], ["xss"])


def test_glob_matches_any_depth():
    kept, exempted = apply_exemptions("PUT", "/api/snippets/a/b", ["rce-indicator"], RULES)
    assert (kept, exempted) == ([], ["rce-indicator"])


def test_only_listed_labels_are_exempted():
    kept, exempted = apply_exemptions("POST", "/api/posts", ["sql-like", "xss"], RULES)
    assert kept == ["sql-like"]
    assert exempted == ["xss"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/posts/../admin",
        "/api/posts/%2e%2e/admin",
        "/api/posts//x",
        "/api/posts\\x",
        "/api/posts;x",
        "/api/posts/./x",
    ],
)
def test_non_canonical_paths_never_exempt(path):
    rules = parse_exemptions("* /api/posts*:xss")
    assert not is_canonical_path(path)
    assert apply_exemptions("POST", path, ["xss"], rules) == (["xss"], [])


def test_rules_default_to_settings(monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(config.settings, payload_exemptions="POST /api/posts:xss"),
    )
    assert apply_exemptions("POST", "/api/posts", ["xss"]) == ([], ["xss"])


def test_invalid_setting_in_development_exempts_nothing(monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        dataclasses.replace(
            config.settings, app_env="development", payload_exemptions="POST /x:bogus"
        ),
    )
    assert apply_exemptions("POST", "/x", ["xss"]) == (["xss"], [])


def test_exempted_labels_add_reason_without_score():
    base = InspectRequest(ip_address="198.51.100.1", method="POST", path="/api/posts")
    exempt = base.model_copy(update={"exempted_indicators": ["xss"]})
    assert calculate_risk(exempt).score == calculate_risk(base).score
    assert "Exempted payload indicator: xss" in calculate_risk(exempt).reasons
