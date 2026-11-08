import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { mapDashboardAlert, mapDashboardEvent } from "./api-map";
import type { BackendEvent } from "./api-types";

function backendEvent(overrides: Partial<BackendEvent> = {}): BackendEvent {
  return {
    event_id: "evt-1",
    timestamp: "2026-11-08T10:00:00Z",
    ip_address: "10.0.0.9",
    path: "/admin",
    method: "GET",
    risk_score: 82,
    decision: "redirect_to_decoy",
    event_type: "admin_probe",
    summary: "",
    ml_shadow: null,
    analyst_label: null,
    analyst_note: "",
    labeled_at: null,
    ...overrides,
  };
}

describe("api mappers", () => {
  it("maps a backend event to the feed shape", () => {
    const event = mapDashboardEvent(backendEvent());
    assert.equal(event.type, "Admin Probe");
    assert.equal(event.severity, "critical");
    assert.equal(event.status, "redirected");
    assert.equal(event.description, "GET /admin");
  });

  it("maps risk bands and decisions at their thresholds", () => {
    const at = (risk_score: number, decision: BackendEvent["decision"]) =>
      mapDashboardEvent(backendEvent({ risk_score, decision }));
    assert.equal(at(29.9, "allow").severity, "low");
    assert.equal(at(30, "allow").severity, "medium");
    assert.equal(at(60, "monitor").severity, "high");
    assert.equal(at(0, "allow").status, "allowed");
    assert.equal(at(0, "monitor").status, "alert");
  });

  it("maps a backend alert without inventing fields", () => {
    assert.deepEqual(
      mapDashboardAlert({
        alert_id: "alt-1",
        severity: "warning",
        title: "Probe",
        description: "Admin path probed",
        recommended_action: "Watch the actor",
        created_at: "2026-11-08T10:00:00Z",
      }),
      {
        id: "alt-1",
        message: "Probe",
        description: "Admin path probed",
        recommendedAction: "Watch the actor",
        severity: "warning",
        timestamp: "2026-11-08T10:00:00Z",
      },
    );
  });
});
