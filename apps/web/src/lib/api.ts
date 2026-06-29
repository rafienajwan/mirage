/**
 * API client for MIRAGE backend gateway.
 * All functions are safe to call from the browser (client components).
 */

import type { ThreatSeverity, ThreatStatus, AlertSeverity } from "@/lib/mock-data";

// ─── Configuration ──────────────────────────────────────────────

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = `${API_URL}/api/v1`;

// ─── Backend response types ─────────────────────────────────────

interface BackendOverview {
  total_requests: number;
  suspicious_requests: number;
  decoy_redirects: number;
  active_alerts: number;
  average_risk_score: number;
}

interface BackendEvent {
  event_id: string;
  timestamp: string;
  ip_address: string;
  path: string;
  method: string;
  risk_score: number;
  decision: "allow" | "monitor" | "redirect_to_decoy";
  event_type: string;
  summary: string;
  ml_shadow: BackendMlShadow | null;
  analyst_label: AnalystLabel | null;
  analyst_note: string;
  labeled_at: string | null;
}

interface BackendMlShadow {
  artifact: string;
  probability: number;
  score: number;
  prediction: string;
  shadow_decision: "allow" | "monitor" | "redirect_to_decoy";
  agrees_with_decision: boolean;
}

interface BackendAlert {
  alert_id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  description: string;
  recommended_action: string;
  created_at: string;
}

interface BackendSimulationResult {
  request_id: string;
  risk_score: number;
  risk_level: string;
  decision: string;
  reasons: string[];
  fingerprint_hash: string;
  decoy_type: string | null;
  ml_shadow: BackendMlShadow | null;
}

interface BackendTrainingDataSummary {
  labeled_rows: number;
  exportable_rows: number;
  minimum_rows: number;
  minimum_rows_per_class: number;
  normal_rows: number;
  suspicious_rows: number;
  has_both_classes: boolean;
  has_minimum_class_rows: boolean;
  ready_for_training: boolean;
  analyst_labels: Record<AnalystLabel, number>;
}

interface BackendMLShadowStatus {
  mode: "disabled" | "missing" | "invalid" | "shadow_ready";
  artifact: string | null;
  shadow_ready: boolean;
  monitor_threshold: number;
  redirect_threshold: number;
  metrics: Record<string, number>;
  blockers: string[];
  warnings: string[];
}

interface BackendRetrainingRun {
  artifact_path: string;
  training_summary: BackendTrainingDataSummary;
  metrics: Record<string, number>;
  review: {
    artifact_path: string;
    artifact_version: number | null;
    shadow_ready: boolean;
    metrics: Record<string, number>;
    blockers: string[];
    warnings: string[];
  };
  next_steps: string[];
}

interface BackendHoneytokenHit {
  hit_id: string;
  timestamp: string;
  event_id: string;
  token_kind: string;
  token_label: string;
  source_ip: string;
  path: string;
  method: string;
  evidence: string;
}

interface BackendHoneytokenSummary {
  total_hits: number;
  hits: BackendHoneytokenHit[];
}

interface BackendActorProfile {
  actor_id: string;
  fingerprint_hash: string;
  source_ip: string;
  first_seen: string;
  last_seen: string;
  request_count: number;
  suspicious_requests: number;
  decoy_redirects: number;
  honeytoken_hits: number;
  max_risk_score: number;
  average_risk_score: number;
  top_paths: string[];
  last_decision: "allow" | "monitor" | "redirect_to_decoy";
  status: "quiet" | "watch" | "suspicious" | "confirmed_interaction";
}

interface BackendActorProfileSummary {
  total_actors: number;
  profiles: BackendActorProfile[];
}

interface BackendActorCluster {
  cluster_id: string;
  label: string;
  status: "quiet" | "watch" | "suspicious" | "confirmed_interaction";
  actor_count: number;
  actor_ids: string[];
  shared_paths: string[];
  max_risk_score: number;
  honeytoken_hits: number;
  decoy_redirects: number;
  last_seen: string;
}

interface BackendActorClusterSummary {
  total_clusters: number;
  clusters: BackendActorCluster[];
}

interface BackendActorCase {
  case_id: string;
  cluster_id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "recommended";
  actor_count: number;
  actor_ids: string[];
  evidence: string[];
  recommended_action: string;
  last_seen: string;
}

interface BackendActorCaseSummary {
  total_cases: number;
  cases: BackendActorCase[];
}

interface BackendActorCaseWorkflow {
  case_id: string;
  cluster_id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "open" | "investigating" | "closed";
  actor_count: number;
  actor_ids: string[];
  evidence: string[];
  recommended_action: string;
  analyst_note: string;
  opened_at: string;
  updated_at: string;
  last_seen: string;
}

interface BackendActorCaseWorkflowSummary {
  total_cases: number;
  cases: BackendActorCaseWorkflow[];
}

// ─── Frontend types (mapped from backend) ───────────────────────

export interface OverviewMetrics {
  totalRequests: number;
  suspiciousRequests: number;
  decoyRedirects: number;
  activeAlerts: number;
  averageRiskScore: number;
}

export interface FeedEvent {
  id: string;
  timestamp: string;
  type: string;
  sourceIp: string;
  endpoint: string;
  riskScore: number;
  severity: ThreatSeverity;
  status: ThreatStatus;
  description: string;
  mlShadow: MLShadow | null;
  analystLabel: AnalystLabel | null;
  analystNote: string;
  labeledAt: string | null;
}

export type AnalystLabel =
  | "normal"
  | "suspicious"
  | "false_positive"
  | "false_negative";

export interface MLShadow {
  artifact: string;
  probability: number;
  score: number;
  prediction: string;
  shadowDecision: ThreatStatus;
  agreesWithDecision: boolean;
}

export interface FeedAlert {
  id: string;
  message: string;
  description: string;
  recommendedAction: string;
  severity: AlertSeverity;
  timestamp: string;
  acknowledged: boolean;
}

export interface SimulationResult {
  requestId: string;
  riskScore: number;
  riskLevel: string;
  decision: string;
  reasons: string[];
  fingerprintHash: string;
  decoyType: string | null;
  mlShadow: MLShadow | null;
}

export interface TrafficPoint {
  hour: number;
  normal: number;
  suspicious: number;
}

export interface RiskHistoryPoint {
  timestamp: string;
  riskScore: number;
}

export interface TrainingDataSummary {
  labeledRows: number;
  exportableRows: number;
  minimumRows: number;
  minimumRowsPerClass: number;
  normalRows: number;
  suspiciousRows: number;
  hasBothClasses: boolean;
  hasMinimumClassRows: boolean;
  readyForTraining: boolean;
  analystLabels: Record<AnalystLabel, number>;
}

export interface MLShadowStatusData {
  mode: "disabled" | "missing" | "invalid" | "shadow_ready";
  artifact: string | null;
  shadowReady: boolean;
  monitorThreshold: number;
  redirectThreshold: number;
  metrics: Record<string, number>;
  blockers: string[];
  warnings: string[];
}

export interface RetrainingRun {
  artifactPath: string;
  trainingSummary: TrainingDataSummary;
  metrics: Record<string, number>;
  review: {
    artifactPath: string;
    artifactVersion: number | null;
    shadowReady: boolean;
    metrics: Record<string, number>;
    blockers: string[];
    warnings: string[];
  };
  nextSteps: string[];
}

export interface HoneytokenHit {
  id: string;
  timestamp: string;
  eventId: string;
  tokenKind: string;
  tokenLabel: string;
  sourceIp: string;
  path: string;
  method: string;
  evidence: string;
}

export interface HoneytokenSummary {
  totalHits: number;
  hits: HoneytokenHit[];
}

export interface ActorProfile {
  id: string;
  fingerprintHash: string;
  sourceIp: string;
  firstSeen: string;
  lastSeen: string;
  requestCount: number;
  suspiciousRequests: number;
  decoyRedirects: number;
  honeytokenHits: number;
  maxRiskScore: number;
  averageRiskScore: number;
  topPaths: string[];
  lastDecision: ThreatStatus;
  status: "quiet" | "watch" | "suspicious" | "confirmed_interaction";
}

export interface ActorProfileSummary {
  totalActors: number;
  profiles: ActorProfile[];
}

export interface ActorCluster {
  id: string;
  label: string;
  status: ActorProfile["status"];
  actorCount: number;
  actorIds: string[];
  sharedPaths: string[];
  maxRiskScore: number;
  honeytokenHits: number;
  decoyRedirects: number;
  lastSeen: string;
}

export interface ActorClusterSummary {
  totalClusters: number;
  clusters: ActorCluster[];
}

export interface ActorCase {
  id: string;
  clusterId: string;
  title: string;
  severity: ThreatSeverity;
  status: "recommended";
  actorCount: number;
  actorIds: string[];
  evidence: string[];
  recommendedAction: string;
  lastSeen: string;
}

export interface ActorCaseSummary {
  totalCases: number;
  cases: ActorCase[];
}

export interface ActorCaseWorkflow {
  id: string;
  clusterId: string;
  title: string;
  severity: ThreatSeverity;
  status: "open" | "investigating" | "closed";
  actorCount: number;
  actorIds: string[];
  evidence: string[];
  recommendedAction: string;
  analystNote: string;
  openedAt: string;
  updatedAt: string;
  lastSeen: string;
}

export interface ActorCaseWorkflowSummary {
  totalCases: number;
  cases: ActorCaseWorkflow[];
}

// ─── Mapping helpers ────────────────────────────────────────────

function mapDecision(decision: string): ThreatStatus {
  switch (decision) {
    case "redirect_to_decoy":
      return "redirected";
    case "monitor":
      return "alert";
    case "allow":
      return "allowed";
    default:
      return "alert";
  }
}

function mapRiskLevel(riskScore: number): ThreatSeverity {
  // Thresholds match backend risk_engine.py: <30 low, <60 medium, <80 high, ≥80 critical
  if (riskScore >= 80) return "critical";
  if (riskScore >= 60) return "high";
  if (riskScore >= 30) return "medium";
  return "low";
}

export function mapDashboardEvent(e: BackendEvent): FeedEvent {
  return {
    id: e.event_id,
    timestamp: e.timestamp,
    type: e.event_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    sourceIp: e.ip_address,
    endpoint: e.path,
    riskScore: e.risk_score,
    severity: mapRiskLevel(e.risk_score),
    status: mapDecision(e.decision),
    description: e.summary || `${e.method} ${e.path}`,
    mlShadow: mapMLShadow(e.ml_shadow),
    analystLabel: e.analyst_label,
    analystNote: e.analyst_note,
    labeledAt: e.labeled_at,
  };
}

function mapMLShadow(shadow: BackendMlShadow | null): MLShadow | null {
  if (!shadow) return null;
  return {
    artifact: shadow.artifact,
    probability: shadow.probability,
    score: shadow.score,
    prediction: shadow.prediction,
    shadowDecision: mapDecision(shadow.shadow_decision),
    agreesWithDecision: shadow.agrees_with_decision,
  };
}

export function mapDashboardAlert(a: BackendAlert): FeedAlert {
  return {
    id: a.alert_id,
    message: a.title,
    description: a.description,
    recommendedAction: a.recommended_action,
    severity: a.severity,
    timestamp: a.created_at,
    acknowledged: false,
  };
}

// ─── Fetcher functions ──────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function simulationFetch<T>(kind: "normal" | "suspicious"): Promise<T> {
  const res = await fetch(`/api/simulate/${kind}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Simulation error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** Fetch dashboard overview metrics. */
export async function fetchOverview(): Promise<OverviewMetrics> {
  const data = await apiFetch<BackendOverview>("/dashboard/overview");
  return {
    totalRequests: data.total_requests,
    suspiciousRequests: data.suspicious_requests,
    decoyRedirects: data.decoy_redirects,
    activeAlerts: data.active_alerts,
    averageRiskScore: data.average_risk_score,
  };
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
  note = "",
): Promise<FeedEvent> {
  const res = await fetch(`/api/events/${encodeURIComponent(eventId)}/label`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, note }),
  });
  if (!res.ok) {
    throw new Error(`Labeling error: ${res.status} ${res.statusText}`);
  }
  return mapDashboardEvent(await res.json());
}

/** Download analyst-labeled feature vectors as JSON Lines. */
export async function downloadTrainingData(): Promise<Blob> {
  const res = await fetch("/api/training-data/export", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Training export error: ${res.status} ${res.statusText}`);
  }
  return res.blob();
}

/** Fetch analyst-labeled training data readiness. */
export async function fetchTrainingDataSummary(): Promise<TrainingDataSummary> {
  const res = await fetch("/api/training-data/summary", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Training summary error: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as BackendTrainingDataSummary;
  return {
    labeledRows: data.labeled_rows,
    exportableRows: data.exportable_rows,
    minimumRows: data.minimum_rows,
    minimumRowsPerClass: data.minimum_rows_per_class,
    normalRows: data.normal_rows,
    suspiciousRows: data.suspicious_rows,
    hasBothClasses: data.has_both_classes,
    hasMinimumClassRows: data.has_minimum_class_rows,
    readyForTraining: data.ready_for_training,
    analystLabels: data.analyst_labels,
  };
}

function mapTrainingSummary(data: BackendTrainingDataSummary): TrainingDataSummary {
  return {
    labeledRows: data.labeled_rows,
    exportableRows: data.exportable_rows,
    minimumRows: data.minimum_rows,
    minimumRowsPerClass: data.minimum_rows_per_class,
    normalRows: data.normal_rows,
    suspiciousRows: data.suspicious_rows,
    hasBothClasses: data.has_both_classes,
    hasMinimumClassRows: data.has_minimum_class_rows,
    readyForTraining: data.ready_for_training,
    analystLabels: data.analyst_labels,
  };
}

/** Train a local shadow-mode candidate from analyst-labeled events. */
export async function runRetraining(): Promise<RetrainingRun> {
  const res = await fetch("/api/training-data/retrain", {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Retraining error: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as BackendRetrainingRun;
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
  const data = await apiFetch<BackendMLShadowStatus>("/dashboard/ml-shadow/status");
  return {
    mode: data.mode,
    artifact: data.artifact,
    shadowReady: data.shadow_ready,
    monitorThreshold: data.monitor_threshold,
    redirectThreshold: data.redirect_threshold,
    metrics: data.metrics,
    blockers: data.blockers,
    warnings: data.warnings,
  };
}

/** Fetch recent honeytoken interactions. */
export async function fetchHoneytokens(): Promise<HoneytokenSummary> {
  const data = await apiFetch<BackendHoneytokenSummary>("/dashboard/honeytokens");
  return {
    totalHits: data.total_hits,
    hits: data.hits.map((hit) => ({
      id: hit.hit_id,
      timestamp: hit.timestamp,
      eventId: hit.event_id,
      tokenKind: hit.token_kind,
      tokenLabel: hit.token_label,
      sourceIp: hit.source_ip,
      path: hit.path,
      method: hit.method,
      evidence: hit.evidence,
    })),
  };
}

/** Fetch recent actor profiles from threat fingerprints. */
export async function fetchActorProfiles(): Promise<ActorProfileSummary> {
  const data = await apiFetch<BackendActorProfileSummary>("/dashboard/actors");
  return {
    totalActors: data.total_actors,
    profiles: data.profiles.map((profile) => ({
      id: profile.actor_id,
      fingerprintHash: profile.fingerprint_hash,
      sourceIp: profile.source_ip,
      firstSeen: profile.first_seen,
      lastSeen: profile.last_seen,
      requestCount: profile.request_count,
      suspiciousRequests: profile.suspicious_requests,
      decoyRedirects: profile.decoy_redirects,
      honeytokenHits: profile.honeytoken_hits,
      maxRiskScore: profile.max_risk_score,
      averageRiskScore: profile.average_risk_score,
      topPaths: profile.top_paths,
      lastDecision: mapDecision(profile.last_decision),
      status: profile.status,
    })),
  };
}

/** Fetch lightweight actor clusters for dashboard triage. */
export async function fetchActorClusters(): Promise<ActorClusterSummary> {
  const data = await apiFetch<BackendActorClusterSummary>("/dashboard/actor-clusters");
  return {
    totalClusters: data.total_clusters,
    clusters: data.clusters.map((cluster) => ({
      id: cluster.cluster_id,
      label: cluster.label,
      status: cluster.status,
      actorCount: cluster.actor_count,
      actorIds: cluster.actor_ids,
      sharedPaths: cluster.shared_paths,
      maxRiskScore: cluster.max_risk_score,
      honeytokenHits: cluster.honeytoken_hits,
      decoyRedirects: cluster.decoy_redirects,
      lastSeen: cluster.last_seen,
    })),
  };
}

/** Fetch read-only recommended actor cases for analyst triage. */
export async function fetchActorCases(): Promise<ActorCaseSummary> {
  const data = await apiFetch<BackendActorCaseSummary>("/dashboard/actor-cases");
  return {
    totalCases: data.total_cases,
    cases: data.cases.map((item) => ({
      id: item.case_id,
      clusterId: item.cluster_id,
      title: item.title,
      severity: item.severity,
      status: item.status,
      actorCount: item.actor_count,
      actorIds: item.actor_ids,
      evidence: item.evidence,
      recommendedAction: item.recommended_action,
      lastSeen: item.last_seen,
    })),
  };
}

function mapActorCaseWorkflow(item: BackendActorCaseWorkflow): ActorCaseWorkflow {
  return {
    id: item.case_id,
    clusterId: item.cluster_id,
    title: item.title,
    severity: item.severity,
    status: item.status,
    actorCount: item.actor_count,
    actorIds: item.actor_ids,
    evidence: item.evidence,
    recommendedAction: item.recommended_action,
    analystNote: item.analyst_note,
    openedAt: item.opened_at,
    updatedAt: item.updated_at,
    lastSeen: item.last_seen,
  };
}

/** Fetch persisted actor case workflow records. */
export async function fetchActorCaseWorkflows(): Promise<ActorCaseWorkflowSummary> {
  const data = await apiFetch<BackendActorCaseWorkflowSummary>("/dashboard/actor-case-workflows");
  return {
    totalCases: data.total_cases,
    cases: data.cases.map(mapActorCaseWorkflow),
  };
}

/** Open a recommended actor case through the server-side API bridge. */
export async function openActorCase(caseId: string, note = ""): Promise<ActorCaseWorkflow> {
  const res = await fetch(`/api/actor-cases/${encodeURIComponent(caseId)}/open`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) {
    throw new Error(`Open actor case error: ${res.status} ${res.statusText}`);
  }
  return mapActorCaseWorkflow(await res.json());
}

/** Update a persisted actor case through the server-side API bridge. */
export async function updateActorCase(
  caseId: string,
  status: ActorCaseWorkflow["status"],
  note = "",
): Promise<ActorCaseWorkflow> {
  const res = await fetch(`/api/actor-case-workflows/${encodeURIComponent(caseId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note }),
  });
  if (!res.ok) {
    throw new Error(`Update actor case error: ${res.status} ${res.statusText}`);
  }
  return mapActorCaseWorkflow(await res.json());
}

/** Fetch active alerts. */
export async function fetchAlerts(): Promise<FeedAlert[]> {
  const { alerts } = await apiFetch<{ alerts: BackendAlert[] }>("/dashboard/alerts");
  return alerts.map(mapDashboardAlert);
}

export type DashboardStreamMessage =
  | {
      type: "snapshot";
      payload: { events: BackendEvent[]; alerts: BackendAlert[] };
    }
  | { type: "event"; payload: BackendEvent }
  | { type: "alert"; payload: BackendAlert };

// ─── Simulation triggers ────────────────────────────────────────

/** Simulate a normal (low-risk) request. */
export async function simulateNormal(): Promise<SimulationResult> {
  const data = await simulationFetch<BackendSimulationResult>("normal");
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

/** Simulate a suspicious (high-risk) request. */
export async function simulateSuspicious(): Promise<SimulationResult> {
  const data = await simulationFetch<BackendSimulationResult>("suspicious");
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

// ─── Chart data fetchers ────────────────────────────────────────

/** Fetch traffic breakdown by hour for the traffic chart. */
export async function fetchTraffic(): Promise<TrafficPoint[]> {
  const { traffic } = await apiFetch<{ traffic: TrafficPoint[] }>("/dashboard/traffic");
  return traffic;
}

/** Fetch recent risk scores for the sparkline chart. */
export async function fetchRiskHistory(): Promise<RiskHistoryPoint[]> {
  const { history } = await apiFetch<{ history: { timestamp: string; risk_score: number }[] }>("/dashboard/risk-history");
  return history.map((h) => ({ timestamp: h.timestamp, riskScore: h.risk_score }));
}

/** Fetch decoy environment status. */
export async function fetchDecoyStatus(): Promise<DecoyStatusData> {
  const data = await apiFetch<{
    active_decoys: number;
    fake_endpoints: string[];
    captured_interactions: number;
    last_decoy_trigger: string | null;
  }>("/decoy/status");
  return {
    activeDecoys: data.active_decoys,
    fakeEndpoints: data.fake_endpoints,
    capturedInteractions: data.captured_interactions,
    lastDecoyTrigger: data.last_decoy_trigger,
  };
}

export interface DecoyStatusData {
  activeDecoys: number;
  fakeEndpoints: string[];
  capturedInteractions: number;
  lastDecoyTrigger: string | null;
}
