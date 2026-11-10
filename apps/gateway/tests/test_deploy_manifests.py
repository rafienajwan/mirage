"""Images and Railway manifests must start correctly on Railway as well as Compose."""

import json
from pathlib import Path

import pytest

APPS = Path(__file__).resolve().parents[2]
SERVICES = {"gateway": 8000, "real-app-demo": 8001, "decoy": 8002}


def _cmd(service: str) -> str:
    lines = (APPS / service / "Dockerfile").read_text(encoding="utf-8").splitlines()
    return next(line for line in lines if line.startswith("CMD "))


@pytest.mark.parametrize("service,port", SERVICES.items())
def test_image_honours_railway_port(service, port):
    assert f"${{PORT:-{port}}}" in _cmd(service)


@pytest.mark.parametrize("service", SERVICES)
def test_image_binds_dual_stack_for_private_networking(service):
    # Railway's private network can be IPv6-only; "::" also accepts IPv4.
    assert "--host ::" in _cmd(service)


@pytest.mark.parametrize("service", SERVICES)
def test_uvicorn_replaces_the_shell(service):
    assert "exec uvicorn" in _cmd(service)


@pytest.mark.parametrize("service", SERVICES)
def test_railway_manifest_checks_health(service):
    manifest = json.loads((APPS / service / "railway.json").read_text(encoding="utf-8"))
    assert manifest["build"]["builder"] == "DOCKERFILE"
    assert manifest["deploy"]["healthcheckPath"] == "/health"


def test_gateway_health_timeout_covers_migrations():
    manifest = json.loads((APPS / "gateway" / "railway.json").read_text(encoding="utf-8"))
    assert manifest["deploy"]["healthcheckTimeout"] >= 30
