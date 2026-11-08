"""Assert the compose stack keeps its network segmentation and privilege limits.

Run from the repository root: ``python infra/check-compose.py``. Requires the
Docker CLI with the compose plugin. Required variables get dummy values so
the file can be rendered without real secrets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess  # noqa: S404 - runs the fixed docker compose command below
import sys

COMPOSE_FILE = Path(__file__).with_name("docker-compose.yml")

REQUIRED = (
    "MIRAGE_API_KEY",
    "MIRAGE_OPERATOR_PASSWORD",
    "MIRAGE_OPERATOR_SESSION_SECRET",
    "MIRAGE_DASHBOARD_TICKET_SECRET",
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    "DECOY_LOGIN_TOKEN",
    "DECOY_OAUTH_TOKEN",
    "DECOY_SERVICE_TOKEN",
    "DECOY_DATABASE_URL",
)

EXPECTED_NETWORKS = {
    "web": {"edge"},
    "gateway": {"edge", "apps", "data"},
    "real-app": {"apps"},
    "decoy": {"apps"},
    "db": {"data"},
}
INTERNAL_NETWORKS = {"apps", "data"}


def render() -> dict:
    env = {**os.environ, **{name: os.environ.get(name, "check-placeholder") for name in REQUIRED}}
    # Fixed argv, no shell; "docker" is resolved from PATH like any CLI step in CI.
    result = subprocess.run(  # noqa: S603
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--format", "json"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout)


def problems(config: dict) -> list[str]:
    found: list[str] = []
    services = config.get("services", {})
    for name, expected in EXPECTED_NETWORKS.items():
        service = services.get(name)
        if service is None:
            found.append(f"service {name} is missing")
            continue
        actual = set(service.get("networks") or {})
        if actual != expected:
            found.append(f"{name} networks are {sorted(actual)}, expected {sorted(expected)}")
    for name, service in services.items():
        if "no-new-privileges:true" not in (service.get("security_opt") or []):
            found.append(f"{name} lacks security_opt no-new-privileges:true")
    networks = config.get("networks", {})
    for name in INTERNAL_NETWORKS:
        if not (networks.get(name) or {}).get("internal"):
            found.append(f"network {name} must be internal")
    return found


def main() -> int:
    found = problems(render())
    for problem in found:
        print(f"FAIL: {problem}")
    if not found:
        print("compose topology OK")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
