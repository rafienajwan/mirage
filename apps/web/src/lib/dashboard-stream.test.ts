import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { mapDashboardSnapshot } from "./api";
import {
  DashboardStreamClient,
  parseDashboardStreamMessage,
  pollIntervalFor,
  reconnectDelay,
} from "./dashboard-stream";

describe("dashboard stream helpers", () => {
  it("uses reconciliation polling only while connected", () => {
    assert.equal(pollIntervalFor("connected"), 60_000);
    assert.equal(pollIntervalFor("connecting"), 10_000);
    assert.equal(pollIntervalFor("disconnected"), 10_000);
  });

  it("caps exponential reconnect delay with deterministic jitter", () => {
    assert.equal(reconnectDelay(0, () => 0.5), 1_000);
    assert.equal(reconnectDelay(4, () => 0.5), 16_000);
    assert.equal(reconnectDelay(20, () => 0.5), 30_000);
  });

  it("rejects malformed messages", () => {
    assert.equal(parseDashboardStreamMessage("bad"), null);
    assert.equal(
      parseDashboardStreamMessage({ type: "snapshot", payload: {} }),
      null,
    );
    assert.equal(
      parseDashboardStreamMessage({
        type: "snapshot",
        payload: { events: [], alerts: [] },
      }),
      null,
    );
  });

  it("maps every complete snapshot panel", () => {
    const backend = {
      events: [],
      alerts: [],
      metrics: {
        total_requests: 1,
        suspicious_requests: 2,
        decoy_redirects: 3,
        active_alerts: 4,
        average_risk_score: 5,
      },
      traffic: [],
      risk_history: [],
      decoy_status: {
        active_decoys: 4,
        fake_endpoints: [],
        captured_interactions: 3,
        last_decoy_trigger: null,
      },
      training_summary: {
        labeled_rows: 0,
        exportable_rows: 0,
        minimum_rows: 20,
        minimum_rows_per_class: 2,
        normal_rows: 0,
        suspicious_rows: 0,
        has_both_classes: false,
        has_minimum_class_rows: false,
        ready_for_training: false,
        analyst_labels: {
          normal: 0,
          suspicious: 0,
          false_positive: 0,
          false_negative: 0,
        },
      },
      ml_shadow_status: {
        mode: "disabled",
        artifact: null,
        shadow_ready: false,
        monitor_threshold: 0.35,
        redirect_threshold: 0.65,
        metrics: {},
        blockers: [],
        warnings: [],
      },
      ml_shadow_summary: {
        inspected_events: 0,
        shadow_events: 0,
        agreements: 0,
        disagreements: 0,
        agreement_rate: 0,
        average_probability: 0,
        average_score: 0,
        live_decisions: { allow: 0, monitor: 0, redirect_to_decoy: 0 },
        shadow_decisions: { allow: 0, monitor: 0, redirect_to_decoy: 0 },
      },
      ml_promotion_readiness: {
        status: "needs_observation",
        artifact: "risk-model.joblib",
        dataset_manifest: "manifest.json",
        dataset_name: "api-domain",
        dataset_version: "v2",
        routing_unchanged: true,
        gates: [
          {
            code: "shadow_event_count",
            passed: false,
            message: "More shadow observations are required",
            actual: 120,
            required: 500,
          },
        ],
        warnings: [],
      },
      honeytokens: { total_hits: 11, hits: [] },
      canary_assignments: { total_assignments: 12, assignments: [] },
      actor_profiles: { total_actors: 13, profiles: [] },
      actor_clusters: { total_clusters: 14, clusters: [] },
      actor_cases: { total_cases: 15, cases: [] },
      actor_case_workflows: { total_cases: 16, cases: [] },
    } as unknown as Parameters<typeof mapDashboardSnapshot>[0];

    const snapshot = mapDashboardSnapshot(backend);

    assert.equal(snapshot.honeytokens.totalHits, 11);
    assert.equal(snapshot.canaryAssignments.totalAssignments, 12);
    assert.equal(snapshot.actorProfiles.totalActors, 13);
    assert.equal(snapshot.actorClusters.totalClusters, 14);
    assert.equal(snapshot.actorCases.totalCases, 15);
    assert.equal(snapshot.actorCaseWorkflows.totalCases, 16);
    assert.equal(snapshot.mlPromotionReadiness.status, "needs_observation");
    assert.equal(
      snapshot.mlPromotionReadiness.gates[0].code,
      "shadow_event_count",
    );
  });

  it("refreshes its ticket on reconnect and reconciles malformed messages", async () => {
    const sockets: FakeSocket[] = [];
    const targets: string[] = [];
    const scheduled: Array<{ callback: () => void; delay: number }> = [];
    const statuses: string[] = [];
    let connectionRequests = 0;
    let reconciliations = 0;

    class FakeSocket {
      onopen: WebSocket["onopen"] = null;
      onmessage: WebSocket["onmessage"] = null;
      onerror: WebSocket["onerror"] = null;
      onclose: WebSocket["onclose"] = null;
      closed = false;

      close() {
        this.closed = true;
      }
    }

    const client = new DashboardStreamClient({
      getConnection: async () => ({
        url: "ws://localhost:8000/api/v1/dashboard/ws",
        token: `ticket-${++connectionRequests}`,
      }),
      createSocket: (target) => {
        const socket = new FakeSocket();
        targets.push(target);
        sockets.push(socket);
        return socket;
      },
      schedule: (callback, delay) => {
        scheduled.push({ callback, delay });
        return callback;
      },
      cancel: () => undefined,
      random: () => 0.5,
      onStatus: (status) => statuses.push(status),
      onMessage: () => {
        throw new Error("mapping failed");
      },
      onReconcile: () => {
        reconciliations += 1;
      },
    });

    client.start();
    await new Promise((resolve) => setTimeout(resolve, 0));
    sockets[0].onopen?.call(sockets[0] as unknown as WebSocket, {} as Event);
    sockets[0].onmessage?.call(
      sockets[0] as unknown as WebSocket,
      { data: "bad" } as MessageEvent,
    );
    sockets[0].onmessage?.call(
      sockets[0] as unknown as WebSocket,
      { data: JSON.stringify({ type: "event", payload: { event_id: "evt-1" } }) } as MessageEvent,
    );
    sockets[0].onclose?.call(
      sockets[0] as unknown as WebSocket,
      {} as CloseEvent,
    );

    assert.deepEqual(statuses, ["connecting", "connected", "disconnected"]);
    assert.equal(reconciliations, 2);
    assert.equal(scheduled[0].delay, 1_000);

    scheduled[0].callback();
    await new Promise((resolve) => setTimeout(resolve, 0));
    sockets[1].onopen?.call(sockets[1] as unknown as WebSocket, {} as Event);
    sockets[1].onclose?.call(
      sockets[1] as unknown as WebSocket,
      {} as CloseEvent,
    );

    assert.equal(scheduled[1].delay, 1_000);
    assert.equal(connectionRequests, 2);
    assert.match(targets[0], /token=ticket-1/);
    assert.match(targets[1], /token=ticket-2/);
    client.stop();
    assert.equal(sockets[1].closed, true);
  });

  it("retries when a fresh connection ticket cannot be obtained", async () => {
    const scheduled: Array<{ callback: () => void; delay: number }> = [];
    const statuses: string[] = [];

    const client = new DashboardStreamClient({
      getConnection: async () => {
        throw new Error("session expired");
      },
      createSocket: () => {
        throw new Error("socket must not be created without a ticket");
      },
      schedule: (callback, delay) => {
        scheduled.push({ callback, delay });
        return callback;
      },
      cancel: () => undefined,
      random: () => 0.5,
      onStatus: (status) => statuses.push(status),
      onMessage: () => undefined,
      onReconcile: () => undefined,
    });

    client.start();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.deepEqual(statuses, ["connecting", "disconnected"]);
    assert.equal(scheduled[0].delay, 1_000);
    client.stop();
  });
});
