import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { describeHttpFailure } from "./http-failure";

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
