import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { gatewayTargetPath, isAllowedBridgeRequest } from "./gateway-bridge";

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
