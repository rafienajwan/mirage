"""End-to-end deployment smoke test, driven against fake services."""

from contextlib import asynccontextmanager
import json
from pathlib import Path
import sqlite3

from alembic.config import Config
from alembic.script import ScriptDirectory
import httpx
import pytest

from scripts import smoke_deploy

GATEWAY = "https://gw.example.test"
WEB = "https://web.example.test"
PASSWORD = "correct-horse-battery-staple"
COOKIE = "signed-session-cookie-value"
TICKET = "signed-stream-ticket-value"
HEAD = ScriptDirectory.from_config(
    Config(str(Path(smoke_deploy.__file__).resolve().parents[1] / "alembic.ini"))
).get_current_head()


def _database(tmp_path, revision=HEAD) -> str:
    path = tmp_path / f"smoke-{revision}.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        connection.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
    return f"sqlite+aiosqlite:///{path.as_posix()}"


class FakeServices:
    """A healthy deployment; tests break one piece at a time."""

    def __init__(self, ws_scheme="wss"):
        self.overrides = {}
        self.requests = []
        self.ws_scheme = ws_scheme

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.host, request.url.path)
        if key in self.overrides:
            return self.overrides[key]
        host, path = request.url.host, request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if host == "gw.example.test" and path == "/api/v1/proxy/api/products":
            return httpx.Response(200, json={"products": [{"id": 1}]})
        if host == "gw.example.test" and path == "/api/v1/proxy/.env":
            return httpx.Response(200, text="APP_ENV=production\nMIRAGE_DECOY_VARIANT=a\n")
        if host == "web.example.test" and path == "/login":
            return httpx.Response(200, text="<html>login</html>")
        if path == "/api/auth/login":
            body = json.loads(request.content)
            if body == {"username": "admin", "password": PASSWORD}:
                return httpx.Response(
                    200,
                    json={"ok": True},
                    headers={"set-cookie": f"mirage_operator_session={COOKIE}; Path=/; HttpOnly"},
                )
            return httpx.Response(401, json={"detail": "Invalid credentials"})
        cookie = request.headers.get("cookie", "")
        if path == "/api/gateway/operators":
            if f"mirage_operator_session={COOKIE}" not in cookie:
                return httpx.Response(401)
            return httpx.Response(200, json={"operators": [{"username": "admin", "role": "admin"}]})
        if path == "/api/dashboard-stream-ticket":
            if f"mirage_operator_session={COOKIE}" not in cookie:
                return httpx.Response(401)
            return httpx.Response(
                200,
                json={
                    "url": f"{self.ws_scheme}://gw.example.test/api/v1/dashboard/ws",
                    "token": TICKET,
                    "expiresAt": 1,
                },
            )
        return httpx.Response(404)


class FakeSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.opened = []

    def __call__(self, url, origin):
        self.opened.append((url, origin))

        @asynccontextmanager
        async def session():
            yield self

        return session()

    async def recv(self):
        if not self.messages:
            raise TimeoutError
        return self.messages.pop(0)


SNAPSHOT = json.dumps({"type": "snapshot", "payload": {}})


def _env(tmp_path, **overrides):
    env = {
        "SMOKE_GATEWAY_URL": GATEWAY,
        "SMOKE_WEB_URL": WEB,
        "SMOKE_OPERATOR_USERNAME": "admin",
        "SMOKE_OPERATOR_PASSWORD": PASSWORD,
    }
    env.update(overrides)
    if "DATABASE_URL" not in overrides:
        env["DATABASE_URL"] = _database(tmp_path)
    return {key: value for key, value in env.items() if value is not None}


def _run(tmp_path, capsys, *, argv=(), services=None, socket=None, **env):
    services = services or FakeServices()
    socket = socket or FakeSocket([SNAPSHOT])
    code = smoke_deploy.main(
        list(argv),
        env=_env(tmp_path, **env),
        transport=httpx.MockTransport(services),
        connect=socket,
    )
    out = capsys.readouterr().out
    lines = {
        _name(line): line
        for line in out.splitlines()
        if line.startswith(("PASS ", "FAIL "))
    }
    return code, out, lines, services, socket


def _name(line: str) -> str:
    return line[5:].split("  ")[0].strip()


def test_healthy_deployment_passes_every_check(tmp_path, capsys):
    code, out, lines, _, _ = _run(tmp_path, capsys)
    assert code == 0
    assert list(lines) == [
        "gateway health",
        "web health",
        "route to real app",
        "route to decoy",
        "operator login",
        "operator API",
        "dashboard stream",
        "database migrated",
    ]
    assert all(line.startswith("PASS ") for line in lines.values()), out


def test_output_never_contains_secrets(tmp_path, capsys):
    _, out, _, _, _ = _run(tmp_path, capsys)
    for secret in (PASSWORD, COOKIE, TICKET, ".db"):
        assert secret not in out


def test_failed_gateway_health_fails_the_run(tmp_path, capsys):
    services = FakeServices()
    services.overrides[("GET", "gw.example.test", "/health")] = httpx.Response(502)
    code, _, lines, _, _ = _run(tmp_path, capsys, services=services)
    assert code == 1
    assert lines["gateway health"].startswith("FAIL ")
    assert "502" in lines["gateway health"]


def test_plain_http_is_refused_without_allow_insecure(tmp_path, capsys):
    code, _, lines, services, _ = _run(
        tmp_path, capsys, SMOKE_GATEWAY_URL="http://gw.example.test"
    )
    assert code == 1
    assert lines["gateway health"].startswith("FAIL ")
    assert "https" in lines["gateway health"]
    assert not [r for r in services.requests if r.url.path == "/health"]


def test_allow_insecure_accepts_http_and_ws(tmp_path, capsys):
    code, out, _, _, _ = _run(
        tmp_path,
        capsys,
        argv=["--allow-insecure"],
        services=FakeServices(ws_scheme="ws"),
        SMOKE_GATEWAY_URL="http://gw.example.test",
        SMOKE_WEB_URL="http://web.example.test",
    )
    assert code == 0, out


def test_ws_stream_url_is_refused_without_allow_insecure(tmp_path, capsys):
    code, _, lines, _, socket = _run(tmp_path, capsys, services=FakeServices(ws_scheme="ws"))
    assert code == 1
    assert lines["dashboard stream"].startswith("FAIL ")
    assert socket.opened == []


def test_upstream_health_is_checked_only_when_given(tmp_path, capsys):
    _, _, lines, _, _ = _run(
        tmp_path, capsys, SMOKE_REAL_APP_URL="https://real.example.test"
    )
    assert lines["real-app health"].startswith("PASS ")
    assert "decoy health" not in lines


def test_real_app_route_must_reach_the_real_app(tmp_path, capsys):
    services = FakeServices()
    services.overrides[("GET", "gw.example.test", "/api/v1/proxy/api/products")] = (
        httpx.Response(200, json={"status": "ok", "result": []})
    )
    code, _, lines, _, _ = _run(tmp_path, capsys, services=services)
    assert code == 1
    assert lines["route to real app"].startswith("FAIL ")


def test_decoy_route_must_reach_the_decoy(tmp_path, capsys):
    services = FakeServices()
    services.overrides[("GET", "gw.example.test", "/api/v1/proxy/.env")] = httpx.Response(
        200, json={"service": "protected-demo-app"}
    )
    code, _, lines, _, _ = _run(tmp_path, capsys, services=services)
    assert code == 1
    assert lines["route to decoy"].startswith("FAIL ")


def test_login_sends_the_web_origin(tmp_path, capsys):
    _, _, _, services, _ = _run(tmp_path, capsys)
    login = next(r for r in services.requests if r.url.path == "/api/auth/login")
    assert login.headers["origin"] == WEB


def test_wrong_password_fails_login_and_dependent_checks(tmp_path, capsys):
    code, out, lines, _, _ = _run(tmp_path, capsys, SMOKE_OPERATOR_PASSWORD="wrong-password")
    assert code == 1
    for name in ("operator login", "operator API", "dashboard stream"):
        assert lines[name].startswith("FAIL "), out
    assert "wrong-password" not in out


def test_missing_credentials_fail(tmp_path, capsys):
    code, _, lines, _, _ = _run(tmp_path, capsys, SMOKE_OPERATOR_PASSWORD=None)
    assert code == 1
    assert "SMOKE_OPERATOR_PASSWORD" in lines["operator login"]


def test_operator_api_must_list_the_user(tmp_path, capsys):
    services = FakeServices()
    services.overrides[("GET", "web.example.test", "/api/gateway/operators")] = (
        httpx.Response(200, json={"operators": []})
    )
    code, _, lines, _, _ = _run(tmp_path, capsys, services=services)
    assert code == 1
    assert lines["operator API"].startswith("FAIL ")


def test_stream_connects_with_ticket_and_web_origin(tmp_path, capsys):
    _, _, _, _, socket = _run(tmp_path, capsys)
    [(url, origin)] = socket.opened
    assert url.startswith("wss://gw.example.test/api/v1/dashboard/ws?token=")
    assert origin == WEB


def test_stream_without_snapshot_fails(tmp_path, capsys):
    code, _, lines, _, _ = _run(
        tmp_path, capsys, socket=FakeSocket([json.dumps({"type": "event"})])
    )
    assert code == 1
    assert lines["dashboard stream"].startswith("FAIL ")


def test_stale_schema_fails(tmp_path, capsys):
    code, _, lines, _, _ = _run(
        tmp_path, capsys, DATABASE_URL=_database(tmp_path, revision="0001_initial")
    )
    assert code == 1
    assert lines["database migrated"].startswith("FAIL ")
    assert HEAD in lines["database migrated"]


def test_missing_database_url_fails(tmp_path, capsys):
    code, _, lines, _, _ = _run(tmp_path, capsys, DATABASE_URL=None)
    assert code == 1
    assert "DATABASE_URL" in lines["database migrated"]


@pytest.mark.parametrize("flag", ["--password", "--operator-password"])
def test_password_is_not_accepted_as_a_flag(flag, tmp_path, capsys):
    with pytest.raises(SystemExit):
        smoke_deploy.parse_args([flag, PASSWORD])
