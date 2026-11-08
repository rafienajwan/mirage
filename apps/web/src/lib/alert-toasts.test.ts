import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { selectNewAlerts } from "./alert-toasts";
import type { FeedAlert } from "./api-types";

function alert(id: string, timestamp: string): FeedAlert {
  return {
    id,
    message: id,
    description: "",
    recommendedAction: "",
    severity: "warning",
    timestamp,
  };
}

const T1 = "2026-11-08T10:00:00Z";
const T2 = "2026-11-08T10:01:00Z";
const T3 = "2026-11-08T10:02:00Z";

describe("selectNewAlerts", () => {
  it("does not toast the alerts present on first load", () => {
    const result = selectNewAlerts([alert("b", T2), alert("a", T1)], null);
    assert.deepEqual(result.fresh, []);
    assert.equal(result.watermark, Date.parse(T2));
  });

  it("does not toast older alerts that were outside the previous window", () => {
    const { watermark } = selectNewAlerts([alert("b", T2)], null);
    const result = selectNewAlerts([alert("b", T2), alert("a", T1)], watermark);
    assert.deepEqual(result.fresh, []);
    assert.equal(result.watermark, Date.parse(T2));
  });

  it("toasts only alerts newer than the newest one already seen", () => {
    const { watermark } = selectNewAlerts([alert("a", T1)], null);
    const result = selectNewAlerts(
      [alert("c", T3), alert("b", T2), alert("a", T1)],
      watermark,
    );
    assert.deepEqual(result.fresh.map((item) => item.id), ["c", "b"]);
    assert.equal(result.watermark, Date.parse(T3));
  });

  it("toasts the first alert when the dashboard started with none", () => {
    const { watermark } = selectNewAlerts([], null);
    const result = selectNewAlerts([alert("a", T1)], watermark);
    assert.deepEqual(result.fresh.map((item) => item.id), ["a"]);
  });

  it("ignores alerts with an unparseable timestamp", () => {
    const { watermark } = selectNewAlerts([alert("a", T1)], null);
    const result = selectNewAlerts([alert("x", "not a date")], watermark);
    assert.deepEqual(result.fresh, []);
    assert.equal(result.watermark, Date.parse(T1));
  });
});
