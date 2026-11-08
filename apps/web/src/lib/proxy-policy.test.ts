import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { decideProxyAccess, type ProxyRequestFacts } from "./proxy-policy";

function facts(overrides: Partial<ProxyRequestFacts> = {}): ProxyRequestFacts {
  return {
    method: "GET",
    pathname: "/api/gateway/dashboard/overview",
    origin: null,
    host: "mirage.example",
    forwardedProto: null,
    protocol: "https:",
    authenticated: true,
    ...overrides,
  };
}

describe("decideProxyAccess", () => {
  it("returns 401 for an API call without a session", () => {
    assert.equal(decideProxyAccess(facts({ authenticated: false })), "unauthorized");
  });

  it("redirects a dashboard page request without a session to login", () => {
    assert.equal(
      decideProxyAccess(facts({ pathname: "/dashboard", authenticated: false })),
      "login",
    );
  });

  it("lets the public auth routes through without a session", () => {
    for (const pathname of ["/api/auth/login", "/api/auth/logout"]) {
      assert.equal(
        decideProxyAccess(
          facts({ pathname, method: "POST", authenticated: false }),
        ),
        "allow",
      );
    }
  });

  it("allows an authenticated GET without an Origin header", () => {
    assert.equal(decideProxyAccess(facts()), "allow");
  });

  it("rejects a cross-origin POST even with a valid session", () => {
    assert.equal(
      decideProxyAccess(
        facts({
          method: "POST",
          pathname: "/api/gateway/simulate/suspicious",
          origin: "https://evil.mirage.example",
        }),
      ),
      "forbidden",
    );
  });

  it("rejects a POST that carries no Origin header", () => {
    assert.equal(
      decideProxyAccess(
        facts({ method: "POST", pathname: "/api/gateway/dashboard/training-data/retrain" }),
      ),
      "forbidden",
    );
  });

  it("allows a same-origin PATCH", () => {
    assert.equal(
      decideProxyAccess(
        facts({
          method: "PATCH",
          pathname: "/api/gateway/dashboard/actor-case-workflows/case-1",
          origin: "https://mirage.example",
        }),
      ),
      "allow",
    );
  });

  it("honours x-forwarded-proto behind a TLS-terminating proxy", () => {
    assert.equal(
      decideProxyAccess(
        facts({
          method: "POST",
          origin: "https://mirage.example",
          protocol: "http:",
          forwardedProto: "https, http",
        }),
      ),
      "allow",
    );
  });
});
