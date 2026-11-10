"""End-to-end smoke test for a deployed MIRAGE stack.

Checks, over HTTPS and WSS, that the gateway and dashboard are up, that the
gateway routes to both upstreams, that an operator can sign in and call the
operator API through the dashboard, that the live stream delivers a
snapshot, and that the database schema is at the Alembic head.

Prints one PASS/FAIL line per check and exits 1 if any check failed. URLs
and the username come from flags or environment variables; the password
comes only from SMOKE_OPERATOR_PASSWORD, never a flag. Nothing secret is
printed: not the password, the session cookie, the stream ticket or the
database URL.

Run from apps/gateway:

    SMOKE_OPERATOR_PASSWORD=... DATABASE_URL=... \\
    python scripts/smoke_deploy.py --gateway-url https://gw.example \\
        --web-url https://dashboard.example --username admin

The decoy check sends one scanner-like request; it is recorded as an attack
event in the dashboard.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any, Awaitable, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit

import httpx

GATEWAY_ROOT = Path(__file__).resolve().parents[1]
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))

SESSION_COOKIE = "mirage_operator_session"
DECOY_PATH = "/api/v1/proxy/.env?id=1%27%20OR%20%271%27%3D%271"
DECOY_USER_AGENT = "sqlmap/1.8 (mirage-smoke-test)"
STREAM_TIMEOUT_SECONDS = 10.0


class Socket(Protocol):
    async def recv(self) -> str | bytes: ...


Connect = Callable[[str, str], AbstractAsyncContextManager[Socket]]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def line(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'} {self.name:<18}  {self.detail}"


class CheckFailed(Exception):
    """A check's expectation was not met; the message is safe to print."""


@dataclass(frozen=True)
class SmokeConfig:
    gateway_url: str | None
    web_url: str | None
    real_app_url: str | None = None
    decoy_url: str | None = None
    username: str | None = None
    password: str | None = None
    database_url: str | None = None
    allow_insecure: bool = False
    timeout: float = 15.0

    def secrets(self) -> list[str]:
        values = [self.password, self.database_url]
        if self.database_url:
            from sqlalchemy.engine import make_url
            from sqlalchemy.exc import ArgumentError

            try:
                values.append(make_url(self.database_url).password)
            except ArgumentError:
                values.append(None)  # unparseable: the whole URL is already hidden
        return [value for value in values if value]


@dataclass
class SmokeState:
    cookie: str | None = None
    hidden: list[str] = field(default_factory=list)

    def hide(self, value: str) -> str:
        self.hidden.append(value)
        return value


def _base(url: str) -> str:
    return url.rstrip("/")


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _require_url(config: SmokeConfig, url: str | None, variable: str) -> str:
    if not url:
        raise CheckFailed(f"{variable} is not set")
    scheme = urlsplit(url).scheme
    if scheme == "https" or (scheme == "http" and config.allow_insecure):
        return _base(url)
    raise CheckFailed(f"{url} must use https (pass --allow-insecure for local http)")


async def _get(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    return await client.get(url, **kwargs)


async def check_health(
    config: SmokeConfig, client: httpx.AsyncClient, url: str | None, variable: str
) -> str:
    base = _require_url(config, url, variable)
    response = await _get(client, f"{base}/health")
    if response.status_code != 200:
        raise CheckFailed(f"{base}/health -> {response.status_code}")
    status = response.json().get("status")
    if status not in {"ok", "healthy"}:
        raise CheckFailed(f"{base}/health -> unexpected status {status!r}")
    return f"{base}/health -> 200"


async def check_web(config: SmokeConfig, client: httpx.AsyncClient) -> str:
    base = _require_url(config, config.web_url, "SMOKE_WEB_URL")
    response = await _get(client, f"{base}/login")
    if response.status_code != 200:
        raise CheckFailed(f"{base}/login -> {response.status_code}")
    return f"{base}/login -> 200"


async def check_real_app_route(config: SmokeConfig, client: httpx.AsyncClient) -> str:
    base = _require_url(config, config.gateway_url, "SMOKE_GATEWAY_URL")
    response = await _get(client, f"{base}/api/v1/proxy/api/products")
    if response.status_code != 200:
        raise CheckFailed(f"proxy /api/products -> {response.status_code}")
    try:
        products = response.json().get("products")
    except ValueError:
        products = None
    if not isinstance(products, list):
        raise CheckFailed("proxy /api/products did not return the real app's product list")
    return "proxy /api/products -> real app"


async def check_decoy_route(config: SmokeConfig, client: httpx.AsyncClient) -> str:
    base = _require_url(config, config.gateway_url, "SMOKE_GATEWAY_URL")
    response = await _get(
        client, f"{base}{DECOY_PATH}", headers={"User-Agent": DECOY_USER_AGENT}
    )
    if response.status_code != 200:
        raise CheckFailed(f"proxy /.env -> {response.status_code}")
    if "MIRAGE_DECOY_VARIANT=" not in response.text:
        raise CheckFailed("proxy /.env was not answered by the decoy")
    return "proxy /.env (scanner) -> decoy"


def _require_credentials(config: SmokeConfig) -> tuple[str, str]:
    if not config.username:
        raise CheckFailed("SMOKE_OPERATOR_USERNAME is not set")
    if not config.password:
        raise CheckFailed("SMOKE_OPERATOR_PASSWORD is not set")
    return config.username, config.password


async def check_login(
    config: SmokeConfig, client: httpx.AsyncClient, state: SmokeState
) -> str:
    base = _require_url(config, config.web_url, "SMOKE_WEB_URL")
    username, password = _require_credentials(config)
    response = await client.post(
        f"{base}/api/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": _origin(base)},
    )
    if response.status_code != 200:
        raise CheckFailed(f"POST /api/auth/login -> {response.status_code}")
    cookie = response.cookies.get(SESSION_COOKIE)
    if not cookie:
        raise CheckFailed("login succeeded but set no session cookie")
    state.cookie = state.hide(cookie)
    return f"signed in as {username}"


def _session_headers(state: SmokeState) -> dict[str, str]:
    if not state.cookie:
        raise CheckFailed("needs a session; operator login failed")
    return {"Cookie": f"{SESSION_COOKIE}={state.cookie}"}


async def check_operator_api(
    config: SmokeConfig, client: httpx.AsyncClient, state: SmokeState
) -> str:
    base = _require_url(config, config.web_url, "SMOKE_WEB_URL")
    headers = _session_headers(state)
    response = await _get(client, f"{base}/api/gateway/operators", headers=headers)
    if response.status_code != 200:
        raise CheckFailed(f"GET /api/gateway/operators -> {response.status_code}")
    names = [entry.get("username") for entry in response.json().get("operators", [])]
    if config.username not in names:
        raise CheckFailed("operator roster does not list the signed-in operator")
    return f"dashboard -> gateway -> database: {len(names)} operator(s)"


async def check_stream(
    config: SmokeConfig, client: httpx.AsyncClient, state: SmokeState, connect: Connect
) -> str:
    base = _require_url(config, config.web_url, "SMOKE_WEB_URL")
    headers = _session_headers(state)
    response = await _get(client, f"{base}/api/dashboard-stream-ticket", headers=headers)
    if response.status_code != 200:
        raise CheckFailed(f"GET /api/dashboard-stream-ticket -> {response.status_code}")
    ticket = response.json()
    url, token = ticket.get("url"), ticket.get("token")
    if not isinstance(url, str) or not isinstance(token, str):
        raise CheckFailed("stream ticket response is missing url or token")
    state.hide(token)
    scheme = urlsplit(url).scheme
    if not (scheme == "wss" or (scheme == "ws" and config.allow_insecure)):
        raise CheckFailed(f"stream URL {url} must use wss (pass --allow-insecure for local ws)")
    target = f"{url}{'&' if '?' in url else '?'}{urlencode({'token': token})}"
    async with connect(target, _origin(base)) as socket:
        message = json.loads(await asyncio.wait_for(socket.recv(), STREAM_TIMEOUT_SECONDS))
    if not isinstance(message, dict) or message.get("type") != "snapshot":
        raise CheckFailed(f"stream sent no snapshot first (got {message.get('type')!r})")
    return f"{url} -> snapshot"


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_config = Config(str(GATEWAY_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(GATEWAY_ROOT / "migrations"))
    heads = ScriptDirectory.from_config(alembic_config).get_heads()
    if len(heads) != 1:
        raise CheckFailed(f"migrations have {len(heads)} heads, expected 1")
    return heads[0]


async def check_database(config: SmokeConfig) -> str:
    if not config.database_url:
        raise CheckFailed("DATABASE_URL is not set")
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.database_url import normalize_database_url

    url = normalize_database_url(config.database_url)
    where = make_url(url).host or "local database"
    head = _alembic_head()
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            revisions = [row[0] for row in result]
    finally:
        await engine.dispose()
    if revisions != [head]:
        raise CheckFailed(f"{where} is at {revisions or 'no revision'}, head is {head}")
    return f"{where} at head {head}"


def _redact(text: str, hidden: list[str]) -> str:
    for value in sorted(hidden, key=len, reverse=True):
        text = text.replace(value, "***")
    return text


async def _run_one(
    name: str, check: Callable[[], Awaitable[str]], hidden: list[str], timeout: float
) -> CheckResult:
    try:
        return CheckResult(name, True, await asyncio.wait_for(check(), timeout))
    except CheckFailed as exc:
        return CheckResult(name, False, _redact(str(exc), hidden))
    except Exception as exc:  # noqa: BLE001 - every failure must become a FAIL line
        detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        return CheckResult(name, False, _redact(detail, hidden))


async def run_checks(
    config: SmokeConfig, client: httpx.AsyncClient, connect: Connect
) -> list[CheckResult]:
    state = SmokeState(hidden=config.secrets())
    checks: list[tuple[str, Callable[[], Awaitable[str]]]] = [
        ("gateway health", lambda: check_health(
            config, client, config.gateway_url, "SMOKE_GATEWAY_URL")),
        ("web health", lambda: check_web(config, client)),
    ]
    if config.real_app_url:
        checks.append(("real-app health", lambda: check_health(
            config, client, config.real_app_url, "SMOKE_REAL_APP_URL")))
    if config.decoy_url:
        checks.append(("decoy health", lambda: check_health(
            config, client, config.decoy_url, "SMOKE_DECOY_URL")))
    checks += [
        ("route to real app", lambda: check_real_app_route(config, client)),
        ("route to decoy", lambda: check_decoy_route(config, client)),
        ("operator login", lambda: check_login(config, client, state)),
        ("operator API", lambda: check_operator_api(config, client, state)),
        ("dashboard stream", lambda: check_stream(config, client, state, connect)),
        ("database migrated", lambda: check_database(config)),
    ]
    return [await _run_one(name, check, state.hidden, config.timeout) for name, check in checks]


def _websocket_connect(url: str, origin: str) -> AbstractAsyncContextManager[Socket]:
    from websockets.asyncio.client import connect

    return connect(url, origin=origin, open_timeout=STREAM_TIMEOUT_SECONDS)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gateway-url", help="Public gateway URL (env SMOKE_GATEWAY_URL)")
    parser.add_argument("--web-url", help="Public dashboard URL (env SMOKE_WEB_URL)")
    parser.add_argument(
        "--real-app-url", help="Optional direct real-app URL (env SMOKE_REAL_APP_URL)"
    )
    parser.add_argument("--decoy-url", help="Optional direct decoy URL (env SMOKE_DECOY_URL)")
    parser.add_argument("--username", help="Operator username (env SMOKE_OPERATOR_USERNAME)")
    parser.add_argument(
        "--allow-insecure",
        action="store_true",
        help="Accept http:// and ws:// (local Compose only)",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Seconds per check")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace, env: Mapping[str, str]) -> SmokeConfig:
    return SmokeConfig(
        gateway_url=args.gateway_url or env.get("SMOKE_GATEWAY_URL"),
        web_url=args.web_url or env.get("SMOKE_WEB_URL"),
        real_app_url=args.real_app_url or env.get("SMOKE_REAL_APP_URL"),
        decoy_url=args.decoy_url or env.get("SMOKE_DECOY_URL"),
        username=args.username or env.get("SMOKE_OPERATOR_USERNAME"),
        password=env.get("SMOKE_OPERATOR_PASSWORD"),
        database_url=env.get("DATABASE_URL"),
        allow_insecure=args.allow_insecure,
        timeout=args.timeout,
    )


async def _main(
    config: SmokeConfig,
    transport: httpx.AsyncBaseTransport | None,
    connect: Connect,
) -> list[CheckResult]:
    async with httpx.AsyncClient(
        transport=transport, timeout=config.timeout, follow_redirects=False
    ) as client:
        return await run_checks(config, client, connect)


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    connect: Connect | None = None,
) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config = build_config(args, os.environ if env is None else env)
    results = asyncio.run(_main(config, transport, connect or _websocket_connect))
    for result in results:
        print(result.line())
    failed = sum(not result.ok for result in results)
    print(f"{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
