/**
 * Browser-side fetchers for the MIRAGE dashboard. Every call goes through
 * the server-side gateway bridge, which adds the API key.
 */

import {
  mapActorCaseSummary,
  mapActorCaseWorkflow,
  mapActorCaseWorkflowSummary,
  mapActorClusterSummary,
  mapActorProfileSummary,
  mapCanaryAssignment,
  mapCanaryAssignmentSummary,
  mapDashboardAlert,
  mapDashboardEvent,
  mapDecoyStatus,
  mapHoneytokenSummary,
  mapMLPromotionReadiness,
  mapMLShadow,
  mapMLShadowStatus,
  mapMLShadowSummary,
  mapOverview,
  mapRiskHistoryPoint,
  mapTrainingSummary,
} from "./api-map";
import type {
  ActorCaseSummary,
  ActorCaseWorkflow,
  ActorCaseWorkflowSummary,
  ActorClusterSummary,
  ActorProfileSummary,
  AnalystLabel,
  BackendActorCaseSummary,
  BackendActorCaseWorkflow,
  BackendActorCaseWorkflowSummary,
  BackendActorClusterSummary,
  BackendActorProfileSummary,
  BackendAlert,
  BackendCanaryAssignment,
  BackendCanaryAssignmentSummary,
  BackendDecoyStatus,
  BackendEvent,
  BackendHoneytokenSummary,
  BackendMLPromotionReadiness,
  BackendMLShadowStatus,
  BackendMLShadowSummary,
  BackendOverview,
  BackendRetrainingRun,
  BackendRiskHistoryPoint,
  BackendSimulationResult,
  BackendTrainingDataSummary,
  CanaryAssignment,
  CanaryAssignmentSummary,
  DecoyStatusData,
  FeedAlert,
  FeedEvent,
  HoneytokenSummary,
  MLPromotionReadinessData,
  MLShadowStatusData,
  MLShadowSummaryData,
  OverviewMetrics,
  RetrainingRun,
  RiskHistoryPoint,
  SimulationResult,
  TrafficPoint,
  TrainingDataSummary,
} from "./api-types";

const API_PREFIX = "/api/gateway";

/** Every gateway call goes through the server-side bridge, which adds the API key. */
async function gatewayRequest(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_PREFIX}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return (await gatewayRequest(path, init)).json();
}

function sendJson(method: "POST" | "PATCH", body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  };
}

/** Fetch dashboard overview metrics. */
export async function fetchOverview(): Promise<OverviewMetrics> {
  return mapOverview(await apiFetch<BackendOverview>("/dashboard/overview"));
}

/** Fetch recent activity events. */
export async function fetchEvents(): Promise<FeedEvent[]> {
  const { events } = await apiFetch<{ events: BackendEvent[] }>("/dashboard/events");
  return events.map(mapDashboardEvent);
}

/** Apply an analyst label through the server-side API bridge. */
export async function labelEvent(
  eventId: string,
  label: AnalystLabel,
): Promise<FeedEvent> {
  return mapDashboardEvent(
    await apiFetch<BackendEvent>(
      `/dashboard/events/${encodeURIComponent(eventId)}/label`,
      sendJson("PATCH", { label }),
    ),
  );
}

/** Download analyst-labeled feature vectors as JSON Lines. */
export async function downloadTrainingData(): Promise<Blob> {
  return (await gatewayRequest("/dashboard/training-data/export")).blob();
}

/** Fetch analyst-labeled training data readiness. */
export async function fetchTrainingDataSummary(): Promise<TrainingDataSummary> {
  return mapTrainingSummary(
    await apiFetch<BackendTrainingDataSummary>("/dashboard/training-data/summary"),
  );
}

/** Train a local shadow-mode candidate from analyst-labeled events. */
export async function runRetraining(): Promise<RetrainingRun> {
  const data = await apiFetch<BackendRetrainingRun>(
    "/dashboard/training-data/retrain",
    sendJson("POST"),
  );
  return {
    artifactPath: data.artifact_path,
    trainingSummary: mapTrainingSummary(data.training_summary),
    metrics: data.metrics,
    review: {
      artifactPath: data.review.artifact_path,
      artifactVersion: data.review.artifact_version,
      shadowReady: data.review.shadow_ready,
      metrics: data.review.metrics,
      blockers: data.review.blockers,
      warnings: data.review.warnings,
    },
    nextSteps: data.next_steps,
  };
}

/** Fetch model-only shadow scoring status. */
export async function fetchMLShadowStatus(): Promise<MLShadowStatusData> {
  return mapMLShadowStatus(
    await apiFetch<BackendMLShadowStatus>("/dashboard/ml-shadow/status"),
  );
}

/** Fetch recent model-only shadow scoring agreement summary. */
export async function fetchMLShadowSummary(): Promise<MLShadowSummaryData> {
  return mapMLShadowSummary(
    await apiFetch<BackendMLShadowSummary>("/dashboard/ml-shadow/summary?limit=1000"),
  );
}

export async function fetchMLPromotionReadiness(): Promise<MLPromotionReadinessData> {
  return mapMLPromotionReadiness(
    await apiFetch<BackendMLPromotionReadiness>("/dashboard/ml-promotion/readiness"),
  );
}

/** Fetch recent honeytoken interactions. */
export async function fetchHoneytokens(): Promise<HoneytokenSummary> {
  const data = await apiFetch<BackendHoneytokenSummary>("/dashboard/honeytokens");
  return mapHoneytokenSummary(data);
}

/** Fetch issued canary assignment lifecycle records. */
export async function fetchCanaryAssignments(): Promise<CanaryAssignmentSummary> {
  const data = await apiFetch<BackendCanaryAssignmentSummary>("/dashboard/canary-assignments");
  return mapCanaryAssignmentSummary(data);
}

/** Revoke an issued canary assignment through the server-side API bridge. */
export async function revokeCanaryAssignment(
  assignmentId: string,
  reason = "",
): Promise<CanaryAssignment> {
  return mapCanaryAssignment(
    await apiFetch<BackendCanaryAssignment>(
      `/dashboard/canary-assignments/${encodeURIComponent(assignmentId)}/revoke`,
      sendJson("POST", { reason }),
    ),
  );
}

/** Fetch recent actor profiles from threat fingerprints. */
export async function fetchActorProfiles(): Promise<ActorProfileSummary> {
  const data = await apiFetch<BackendActorProfileSummary>("/dashboard/actors");
  return mapActorProfileSummary(data);
}

/** Fetch lightweight actor clusters for dashboard triage. */
export async function fetchActorClusters(): Promise<ActorClusterSummary> {
  const data = await apiFetch<BackendActorClusterSummary>("/dashboard/actor-clusters");
  return mapActorClusterSummary(data);
}

/** Fetch read-only recommended actor cases for analyst triage. */
export async function fetchActorCases(): Promise<ActorCaseSummary> {
  const data = await apiFetch<BackendActorCaseSummary>("/dashboard/actor-cases");
  return mapActorCaseSummary(data);
}

/** Fetch persisted actor case workflow records. */
export async function fetchActorCaseWorkflows(): Promise<ActorCaseWorkflowSummary> {
  const data = await apiFetch<BackendActorCaseWorkflowSummary>("/dashboard/actor-case-workflows");
  return mapActorCaseWorkflowSummary(data);
}

/** Open a recommended actor case through the server-side API bridge. */
export async function openActorCase(
  caseId: string,
  note = "",
  assignedTo = "",
): Promise<ActorCaseWorkflow> {
  return mapActorCaseWorkflow(
    await apiFetch<BackendActorCaseWorkflow>(
      `/dashboard/actor-cases/${encodeURIComponent(caseId)}/open`,
      sendJson("POST", { note, assigned_to: assignedTo }),
    ),
  );
}

/** Update a persisted actor case through the server-side API bridge. */
export async function updateActorCase(
  caseId: string,
  status: ActorCaseWorkflow["status"],
  note = "",
  assignedTo?: string,
): Promise<ActorCaseWorkflow> {
  return mapActorCaseWorkflow(
    await apiFetch<BackendActorCaseWorkflow>(
      `/dashboard/actor-case-workflows/${encodeURIComponent(caseId)}`,
      sendJson("PATCH", { status, note, assigned_to: assignedTo }),
    ),
  );
}

/** Fetch active alerts. */
export async function fetchAlerts(): Promise<FeedAlert[]> {
  const { alerts } = await apiFetch<{ alerts: BackendAlert[] }>("/dashboard/alerts?limit=20");
  return alerts.map(mapDashboardAlert);
}

/** Send a safe simulated normal or suspicious request through the gateway. */
export async function simulateRequest(
  kind: "normal" | "suspicious",
): Promise<SimulationResult> {
  const data = await apiFetch<BackendSimulationResult>(
    `/simulate/${kind}`,
    sendJson("POST"),
  );
  return {
    requestId: data.request_id,
    riskScore: data.risk_score,
    riskLevel: data.risk_level,
    decision: data.decision,
    reasons: data.reasons,
    fingerprintHash: data.fingerprint_hash,
    decoyType: data.decoy_type,
    mlShadow: mapMLShadow(data.ml_shadow),
  };
}

/** Fetch traffic breakdown by hour for the traffic chart. */
export async function fetchTraffic(): Promise<TrafficPoint[]> {
  const { traffic } = await apiFetch<{ traffic: TrafficPoint[] }>("/dashboard/traffic");
  return traffic;
}

/** Fetch recent risk scores for the sparkline chart. */
export async function fetchRiskHistory(): Promise<RiskHistoryPoint[]> {
  const { history } = await apiFetch<{ history: BackendRiskHistoryPoint[] }>("/dashboard/risk-history");
  return history.map(mapRiskHistoryPoint);
}

/** Fetch decoy environment status. */
export async function fetchDecoyStatus(): Promise<DecoyStatusData> {
  return mapDecoyStatus(await apiFetch<BackendDecoyStatus>("/decoy/status"));
}
