import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { safeNextPath } from "./safe-next-path";

const ORIGIN = "https://mirage.example";

describe("safeNextPath", () => {
  it("keeps a same-origin path with query and hash", () => {
    assert.equal(safeNextPath("/dashboard?x=1#a", ORIGIN), "/dashboard?x=1#a");
  });

  for (const target of [
    "/\\evil.com",
    "//evil.com",
    "https://evil.com",
    "javascript:alert(1)",
    "",
    null,
  ]) {
    it(`falls back to /dashboard for ${JSON.stringify(target)}`, () => {
      assert.equal(safeNextPath(target, ORIGIN), "/dashboard");
    });
  }
});
