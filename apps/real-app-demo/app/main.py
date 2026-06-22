"""Small protected application used to demonstrate normal proxy traffic."""

from __future__ import annotations

from fastapi import FastAPI, Request

app = FastAPI(title="MIRAGE Protected Demo App", docs_url=None, redoc_url=None)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/products")
async def products() -> dict:
    return {
        "products": [
            {"id": 1, "name": "Sentinel Basic", "price": 29},
            {"id": 2, "name": "Sentinel Pro", "price": 79},
        ]
    }


@app.get("/api/users/me")
async def current_user() -> dict:
    return {"id": 42, "name": "Demo Operator", "role": "analyst"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def application_route(path: str, request: Request) -> dict:
    return {
        "service": "protected-demo-app",
        "method": request.method,
        "path": "/" + path,
        "status": "ok",
    }
