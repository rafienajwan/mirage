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
  normal_rows: number;
  suspicious_rows: number;
  has_both_classes: boolean;
  ready_for_training: boolean;
  analyst_labels: Record<AnalystLabel, number>;
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
  normalRows: number;
  suspiciousRows: number;
  hasBothClasses: boolean;
  readyForTraining: boolean;
  analystLabels: Record<AnalystLabel, number>;
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

function mapEvent(e: BackendEvent): FeedEvent {
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

function mapAlert(a: BackendAlert): FeedAlert {
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
  return events.map(mapEvent);
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
  return mapEvent(await res.json());
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
    normalRows: data.normal_rows,
    suspiciousRows: data.suspicious_rows,
    hasBothClasses: data.has_both_classes,
    readyForTraining: data.ready_for_training,
    analystLabels: data.analyst_labels,
  };
}

/** Fetch active alerts. */
export async function fetchAlerts(): Promise<FeedAlert[]> {
  const { alerts } = await apiFetch<{ alerts: BackendAlert[] }>("/dashboard/alerts");
  return alerts.map(mapAlert);
}

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
