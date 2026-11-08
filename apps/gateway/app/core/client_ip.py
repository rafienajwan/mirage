"""Resolve the real client address when the gateway sits behind reverse proxies.

Forwarded headers are honored only from peers listed in ``TRUSTED_PROXIES``;
anyone else can write any ``X-Forwarded-For`` they like.
"""

from __future__ import annotations

from functools import lru_cache
import ipaddress
import logging

from starlette.requests import Request

from app.core import config

logger = logging.getLogger(__name__)

Network = ipaddress.IPv4Network | ipaddress.IPv6Network
Address = ipaddress.IPv4Address | ipaddress.IPv6Address


@lru_cache(maxsize=8)
def parse_trusted_proxies(raw: str) -> tuple[Network, ...]:
    """Parse comma-separated IPs or CIDRs; raise ValueError on a bad entry."""
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if entry:
            networks.append(ipaddress.ip_network(entry, strict=False))
    return tuple(networks)


def _parse_address(value: str) -> Address | None:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    # A dual-stack listener reports IPv4 peers as ::ffff:a.b.c.d.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _trusted_networks() -> tuple[Network, ...]:
    try:
        return parse_trusted_proxies(config.settings.trusted_proxies)
    except ValueError:
        # Production refuses to start with a bad value; elsewhere, trust nobody
        # rather than failing every request.
        logger.warning("Ignoring invalid TRUSTED_PROXIES")
        return ()


def _is_trusted(address: Address, networks: tuple[Network, ...]) -> bool:
    return any(address in network for network in networks)


def client_ip(request: Request) -> str:
    """Return the client address, walking X-Forwarded-For through trusted hops."""
    if request.client is None:
        return "unknown"
    peer = request.client.host
    networks = _trusted_networks()
    peer_address = _parse_address(peer)
    if peer_address is None or not _is_trusted(peer_address, networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer

    last_trusted = peer
    for entry in reversed(forwarded.split(",")):
        address = _parse_address(entry)
        if address is None:
            return last_trusted
        if not _is_trusted(address, networks):
            return str(address)
        last_trusted = str(address)
    return last_trusted
