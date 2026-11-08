import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  describeHttpFailure,
  SessionExpiredError,
  summarizeFailures,
} from "./http-failure";

describe("describeHttpFailure", () => {
  it("flags a 401 as an expired session", () => {
    const failure = describeHttpFailure(401, '{"detail":"Authentication required"}');
    assert.equal(failure.sessionExpired, true);
  });

  it("uses the gateway detail message when there is one", () => {
    const failure = describeHttpFailure(404, '{"detail":"Actor case not found"}');
    assert.equal(failure.sessionExpired, false);
    assert.equal(failure.message, "Actor case not found (HTTP 404)");
  });

  it("summarises FastAPI validation errors", () => {
    const failure = describeHttpFailure(
      422,
      '{"detail":[{"msg":"Input should be \'open\' or \'closed\'"}]}',
    );
    assert.equal(failure.message, "Input should be 'open' or 'closed' (HTTP 422)");
  });

  it("falls back to the status when the body is not JSON", () => {
    const failure = describeHttpFailure(502, "<html>Bad gateway</html>");
    assert.equal(failure.message, "Request failed (HTTP 502)");
  });
});

describe("summarizeFailures", () => {
  const ok = { status: "fulfilled", value: 1 } as const;
  const failed = (reason: unknown) => ({ status: "rejected", reason }) as const;

  it("returns null when every request succeeded", () => {
    assert.equal(summarizeFailures([ok, ok]), null);
  });

  it("reports how many requests failed and the first reason", () => {
    const error = summarizeFailures([
      ok,
      failed(new Error("Gateway is unavailable (HTTP 502)")),
      failed(new Error("other")),
    ]);
    assert.ok(error instanceof Error);
    assert.equal(
      error.message,
      "2 of 3 dashboard requests failed. Gateway is unavailable (HTTP 502)",
    );
  });

  it("prefers an expired session so the caller can redirect to login", () => {
    const expired = new SessionExpiredError();
    assert.equal(summarizeFailures([failed(new Error("x")), failed(expired)]), expired);
  });
});
