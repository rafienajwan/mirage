"""Client IP resolution behind trusted reverse proxies."""

import dataclasses

import pytest
from starlette.requests import Request

from app.core import config
from app.core.client_ip import client_ip, parse_trusted_proxies


def _request(peer: str | None, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {"type": "http", "headers": headers}
    if peer is not None:
        scope["client"] = (peer, 1234)
    return Request(scope)


@pytest.fixture
def trust(monkeypatch):
    def _trust(raw: str) -> None:
        monkeypatch.setattr(
            config, "settings", dataclasses.replace(config.settings, trusted_proxies=raw)
        )

    _trust("")
    return _trust


def test_untrusted_peer_ignores_forged_header(trust):
    assert client_ip(_request("203.0.113.5", "1.2.3.4")) == "203.0.113.5"


def test_trusted_peer_returns_rightmost_untrusted_hop(trust):
    trust("10.0.0.0/8")
    request = _request("10.0.0.2", "198.51.100.7, 203.0.113.9, 10.0.0.3")
    assert client_ip(request) == "203.0.113.9"


def test_all_hops_trusted_returns_leftmost(trust):
    trust("10.0.0.0/8")
    assert client_ip(_request("10.0.0.2", "10.0.0.9, 10.0.0.3")) == "10.0.0.9"


def test_trusted_peer_without_header_returns_peer(trust):
    trust("10.0.0.0/8")
    assert client_ip(_request("10.0.0.2")) == "10.0.0.2"


def test_malformed_entry_stops_walk(trust):
    trust("10.0.0.0/8")
    request = _request("10.0.0.2", "198.51.100.7, garbage, 10.0.0.3")
    assert client_ip(request) == "10.0.0.3"


def test_entry_with_port_is_malformed(trust):
    trust("10.0.0.0/8")
    assert client_ip(_request("10.0.0.2", "203.0.113.9:1234")) == "10.0.0.2"


def test_spaces_are_stripped(trust):
    trust("10.0.0.0/8")
    assert client_ip(_request("10.0.0.2", " 198.51.100.7 ")) == "198.51.100.7"


def test_ipv6_trusted_proxy(trust):
    trust("fd00::/8")
    assert client_ip(_request("fd00::1", "2001:db8::5")) == "2001:db8::5"


def test_missing_peer_is_unknown(trust):
    assert client_ip(_request(None)) == "unknown"


def test_parse_trusted_proxies():
    assert len(parse_trusted_proxies("10.0.0.1, 172.16.0.0/12")) == 2
    assert parse_trusted_proxies("") == ()
    assert parse_trusted_proxies("   ") == ()
    with pytest.raises(ValueError):
        parse_trusted_proxies("nope")


def test_invalid_trusted_proxies_falls_back_to_peer(trust):
    trust("nginx")
    assert client_ip(_request("10.0.0.2", "203.0.113.9")) == "10.0.0.2"


def test_ipv4_mapped_peer_matches_ipv4_proxy(trust):
    trust("10.0.0.0/8")
    assert client_ip(_request("::ffff:10.0.0.2", "203.0.113.9")) == "203.0.113.9"
