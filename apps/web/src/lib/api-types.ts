/**
 * Shared types for the MIRAGE dashboard: Backend* mirror gateway JSON,
 * the rest are the UI shapes the mappers produce.
 */

export type ThreatSeverity = "low" | "medium" | "high" | "critical";
export type ThreatStatus = "allowed" | "redirected" | "alert";
export type AlertSeverity = "info" | "warning" | "critical";

export interface BackendOverview {
  total_requests: number;
  suspicious_requests: number;
  decoy_redirects: number;
  active_alerts: number;
  average_risk_score: number;
}

export interface BackendEvent {
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
  labeled_by?: string | null;
}

export interface BackendMlShadow {
  artifact: string;
  probability: number;
  score: number;
  prediction: string;
  shadow_decision: "allow" | "monitor" | "redirect_to_decoy";
  agrees_with_decision: boolean;
}

export interface BackendAlert {
  alert_id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  description: string;
  recommended_action: string;
  created_at: string;
}

export interface BackendSimulationResult {
  request_id: string;
  risk_score: number;
  risk_level: string;
  decision: string;
  reasons: string[];
  fingerprint_hash: string;
  decoy_type: string | null;
  ml_shadow: BackendMlShadow | null;
}

export interface BackendTrainingDataSummary {
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

export interface BackendMLShadowStatus {
  mode: "disabled" | "missing" | "invalid" | "shadow_ready";
  artifact: string | null;
  shadow_ready: boolean;
  monitor_threshold: number;
  redirect_threshold: number;
  metrics: Record<string, number>;
  blockers: string[];
  warnings: string[];
}

export interface BackendMLShadowDecisionBreakdown {
  allow: number;
  monitor: number;
  redirect_to_decoy: number;
}

export interface BackendMLShadowSummary {
  inspected_events: number;
  shadow_events: number;
  agreements: number;
  disagreements: number;
  agreement_rate: number;
  average_probability: number;
  average_score: number;
  live_decisions: BackendMLShadowDecisionBreakdown;
  shadow_decisions: BackendMLShadowDecisionBreakdown;
}

export interface BackendMLPromotionGate {
  code: string;
  passed: boolean;
  message: string;
  actual: number | string | null;
  required: number | string | null;
}

export interface BackendMLPromotionReadiness {
  status: "unavailable" | "blocked" | "needs_observation" | "eligible";
  artifact: string | null;
  dataset_manifest: string | null;
  dataset_name: string | null;
  dataset_version: string | null;
  routing_unchanged: boolean;
  gates: BackendMLPromotionGate[];
  warnings: string[];
}

export interface BackendRetrainingRun {
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

export interface BackendHoneytokenHit {
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

export interface BackendHoneytokenSummary {
  total_hits: number;
  hits: BackendHoneytokenHit[];
}

export interface BackendCanaryAssignment {
  assignment_id: string;
  actor_id: string;
  token_kind: string;
  token_label: string;
  token_hash: string;
  rotation_epoch: string;
  decoy_type: string;
  source_path: string;
  status: "active" | "revoked";
  issued_at: string;
  last_seen_at: string;
  revoked_at: string | null;
  revoke_reason: string;
}

export interface BackendCanaryAssignmentSummary {
  total_assignments: number;
  assignments: BackendCanaryAssignment[];
}

export interface BackendActorProfile {
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

export interface BackendActorProfileSummary {
  total_actors: number;
  profiles: BackendActorProfile[];
}

export interface BackendActorCluster {
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

export interface BackendActorClusterSummary {
  total_clusters: number;
  clusters: BackendActorCluster[];
}

export interface BackendActorCase {
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

export interface BackendActorCaseSummary {
  total_cases: number;
  cases: BackendActorCase[];
}

export interface BackendActorCaseWorkflow {
  case_id: string;
  cluster_id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "open" | "investigating" | "closed";
  actor_count: number;
  actor_ids: string[];
  evidence: string[];
  recommended_action: string;
  assigned_to: string;
  analyst_note: string;
  opened_at: string;
  updated_at: string;
  updated_by?: string | null;
  last_seen: string;
}

export interface BackendActorCaseWorkflowSummary {
  total_cases: number;
  cases: BackendActorCaseWorkflow[];
}

export interface BackendDecoyStatus {
  active_decoys: number;
  fake_endpoints: string[];
  captured_interactions: number;
  last_decoy_trigger: string | null;
}

export interface BackendRiskHistoryPoint {
  timestamp: string;
  risk_score: number;
}

export interface BackendDashboardSnapshot {
  events: BackendEvent[];
  alerts: BackendAlert[];
  metrics: BackendOverview;
  traffic: TrafficPoint[];
  risk_history: BackendRiskHistoryPoint[];
  decoy_status: BackendDecoyStatus;
  training_summary: BackendTrainingDataSummary;
  ml_shadow_status: BackendMLShadowStatus;
  ml_shadow_summary: BackendMLShadowSummary;
  ml_promotion_readiness: BackendMLPromotionReadiness;
  honeytokens: BackendHoneytokenSummary;
  canary_assignments: BackendCanaryAssignmentSummary;
  actor_profiles: BackendActorProfileSummary;
  actor_clusters: BackendActorClusterSummary;
  actor_cases: BackendActorCaseSummary;
  actor_case_workflows: BackendActorCaseWorkflowSummary;
}

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
  labeledBy: string | null;
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

export interface MLShadowDecisionBreakdown {
  allow: number;
  monitor: number;
  redirectToDecoy: number;
}

export interface MLShadowSummaryData {
  inspectedEvents: number;
  shadowEvents: number;
  agreements: number;
  disagreements: number;
  agreementRate: number;
  averageProbability: number;
  averageScore: number;
  liveDecisions: MLShadowDecisionBreakdown;
  shadowDecisions: MLShadowDecisionBreakdown;
}

export interface MLPromotionGate {
  code: string;
  passed: boolean;
  message: string;
  actual: number | string | null;
  required: number | string | null;
}

export interface MLPromotionReadinessData {
  status: "unavailable" | "blocked" | "needs_observation" | "eligible";
  artifact: string | null;
  datasetManifest: string | null;
  datasetName: string | null;
  datasetVersion: string | null;
  routingUnchanged: boolean;
  gates: MLPromotionGate[];
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

export interface CanaryAssignment {
  id: string;
  actorId: string;
  tokenKind: string;
  tokenLabel: string;
  tokenHash: string;
  rotationEpoch: string;
  decoyType: string;
  sourcePath: string;
  status: "active" | "revoked";
  issuedAt: string;
  lastSeenAt: string;
  revokedAt: string | null;
  revokeReason: string;
}

export interface CanaryAssignmentSummary {
  totalAssignments: number;
  assignments: CanaryAssignment[];
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
  assignedTo: string;
  analystNote: string;
  openedAt: string;
  updatedAt: string;
  updatedBy: string | null;
  lastSeen: string;
}

export type OperatorRole = "analyst" | "admin";

export interface OperatorSummary {
  username: string;
  role: OperatorRole;
}

export interface OperatorSession {
  username: string;
  role: OperatorRole;
}

export interface ActorCaseWorkflowSummary {
  totalCases: number;
  cases: ActorCaseWorkflow[];
}

export interface DashboardSnapshot {
  events: FeedEvent[];
  alerts: FeedAlert[];
  overview: OverviewMetrics;
  traffic: TrafficPoint[];
  riskHistory: RiskHistoryPoint[];
  decoyStatus: DecoyStatusData;
  trainingSummary: TrainingDataSummary;
  mlShadowStatus: MLShadowStatusData;
  mlShadowSummary: MLShadowSummaryData;
  mlPromotionReadiness: MLPromotionReadinessData;
  honeytokens: HoneytokenSummary;
  canaryAssignments: CanaryAssignmentSummary;
  actorProfiles: ActorProfileSummary;
  actorClusters: ActorClusterSummary;
  actorCases: ActorCaseSummary;
  actorCaseWorkflows: ActorCaseWorkflowSummary;
}

export type DashboardStreamMessage =
  | {
      type: "snapshot";
      payload: BackendDashboardSnapshot;
    }
  | { type: "event"; payload: BackendEvent }
  | { type: "alert"; payload: BackendAlert };

export interface DecoyStatusData {
  activeDecoys: number;
  fakeEndpoints: string[];
  capturedInteractions: number;
  lastDecoyTrigger: string | null;
}
