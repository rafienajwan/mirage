import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { bridgeHeaders, gatewayTargetPath, isAllowedBridgeRequest } from "./gateway-bridge";

const split = (path: string) => path.split("/");

describe("isAllowedBridgeRequest", () => {
  for (const [method, path] of [
    ["PATCH", "dashboard/events/evt-1/label"],
    ["PATCH", "dashboard/actor-case-workflows/case-1"],
    ["POST", "dashboard/canary-assignments/asg-1/revoke"],
    ["POST", "dashboard/actor-cases/case-1/open"],
    ["POST", "simulate/normal"],
    ["POST", "simulate/suspicious"],
    ["POST", "dashboard/training-data/retrain"],
    ["GET", "dashboard/overview"],
    ["GET", "dashboard/training-data/export"],
  ] as const) {
    it(`allows ${method} ${path}`, () => {
      assert.equal(isAllowedBridgeRequest(method, split(path)), true);
    });
  }

  for (const [method, path] of [
    ["POST", "dashboard/overview"],
    ["POST", "simulate/other"],
    ["PATCH", "dashboard/events/evt-1/label/extra"],
    ["POST", "dashboard/events/evt-1/label"],
    ["PATCH", "dashboard/canary-assignments/asg-1/revoke"],
    ["DELETE", "dashboard/actor-case-workflows/case-1"],
    ["PUT", "dashboard/actor-case-workflows/case-1"],
    ["PATCH", "dashboard/events/../../x"],
    ["PATCH", "dashboard/events/../label"],
    ["POST", "dashboard/actor-cases/./open"],
    ["GET", "dashboard/../../internal"],
    ["GET", ".."],
    ["GET", "dashboard//overview"],
  ] as const) {
    it(`rejects ${method} ${path}`, () => {
      assert.equal(isAllowedBridgeRequest(method, split(path)), false);
    });
  }
});

describe("gatewayTargetPath", () => {
  it("encodes each segment under /api/v1", () => {
    assert.equal(
      gatewayTargetPath(["dashboard", "events", "a/b c", "label"]),
      "/api/v1/dashboard/events/a%2Fb%20c/label",
    );
  });
});

describe("operator routes", () => {
  it("forwards only the roster read", () => {
    assert.equal(isAllowedBridgeRequest("GET", ["operators"]), true);
    assert.equal(isAllowedBridgeRequest("GET", ["operators", "audit"]), false);
    assert.equal(isAllowedBridgeRequest("POST", ["operators", "login"]), false);
  });
});

describe("bridgeHeaders", () => {
  it("sends the key, the operator and the content type, nothing else", () => {
    assert.deepEqual(
      bridgeHeaders({ apiKey: "key", operator: "alice", contentType: "application/json" }),
      {
        "X-Mirage-API-Key": "key",
        "X-Mirage-Operator": "alice",
        "Content-Type": "application/json",
      },
    );
  });

  it("omits the content type when the request has none", () => {
    assert.deepEqual(
      bridgeHeaders({ apiKey: "key", operator: "alice", contentType: null }),
      { "X-Mirage-API-Key": "key", "X-Mirage-Operator": "alice" },
    );
  });
});
