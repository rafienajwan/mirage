/** Pure Backend -> UI mappers for gateway responses. */

import type {
  ActorCaseSummary,
  ActorCaseWorkflow,
  ActorCaseWorkflowSummary,
  ActorClusterSummary,
  ActorProfileSummary,
  BackendActorCaseSummary,
  BackendActorCaseWorkflow,
  BackendActorCaseWorkflowSummary,
  BackendActorClusterSummary,
  BackendActorProfileSummary,
  BackendAlert,
  BackendCanaryAssignment,
  BackendCanaryAssignmentSummary,
  BackendDashboardSnapshot,
  BackendDecoyStatus,
  BackendEvent,
  BackendHoneytokenSummary,
  BackendMLPromotionReadiness,
  BackendMLShadowDecisionBreakdown,
  BackendMLShadowStatus,
  BackendMLShadowSummary,
  BackendMlShadow,
  BackendOverview,
  BackendRiskHistoryPoint,
  BackendTrainingDataSummary,
  CanaryAssignment,
  CanaryAssignmentSummary,
  DashboardSnapshot,
  DecoyStatusData,
  FeedAlert,
  FeedEvent,
  HoneytokenSummary,
  MLPromotionReadinessData,
  MLShadow,
  MLShadowDecisionBreakdown,
  MLShadowStatusData,
  MLShadowSummaryData,
  OverviewMetrics,
  RiskHistoryPoint,
  ThreatSeverity,
  ThreatStatus,
  TrainingDataSummary,
} from "./api-types";

export function mapDecision(decision: string): ThreatStatus {
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

export function mapRiskLevel(riskScore: number): ThreatSeverity {
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
    labeledBy: e.labeled_by ?? null,
  };
}

export function mapMLShadow(shadow: BackendMlShadow | null): MLShadow | null {
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
  };
}

export function mapOverview(data: BackendOverview): OverviewMetrics {
  return {
    totalRequests: data.total_requests,
    suspiciousRequests: data.suspicious_requests,
    decoyRedirects: data.decoy_redirects,
    activeAlerts: data.active_alerts,
    averageRiskScore: data.average_risk_score,
  };
}

export function mapTrainingSummary(data: BackendTrainingDataSummary): TrainingDataSummary {
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

export function mapMLShadowStatus(data: BackendMLShadowStatus): MLShadowStatusData {
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

export function mapMLShadowBreakdown(
  data: BackendMLShadowDecisionBreakdown,
): MLShadowDecisionBreakdown {
  return {
    allow: data.allow,
    monitor: data.monitor,
    redirectToDecoy: data.redirect_to_decoy,
  };
}

export function mapMLShadowSummary(data: BackendMLShadowSummary): MLShadowSummaryData {
  return {
    inspectedEvents: data.inspected_events,
    shadowEvents: data.shadow_events,
    agreements: data.agreements,
    disagreements: data.disagreements,
    agreementRate: data.agreement_rate,
    averageProbability: data.average_probability,
    averageScore: data.average_score,
    liveDecisions: mapMLShadowBreakdown(data.live_decisions),
    shadowDecisions: mapMLShadowBreakdown(data.shadow_decisions),
  };
}

export function mapMLPromotionReadiness(
  data: BackendMLPromotionReadiness,
): MLPromotionReadinessData {
  return {
    status: data.status,
    artifact: data.artifact,
    datasetManifest: data.dataset_manifest,
    datasetName: data.dataset_name,
    datasetVersion: data.dataset_version,
    routingUnchanged: data.routing_unchanged,
    gates: data.gates,
    warnings: data.warnings,
  };
}

export function mapHoneytokenSummary(
  data: BackendHoneytokenSummary,
): HoneytokenSummary {
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

export function mapCanaryAssignment(item: BackendCanaryAssignment): CanaryAssignment {
  return {
    id: item.assignment_id,
    actorId: item.actor_id,
    tokenKind: item.token_kind,
    tokenLabel: item.token_label,
    tokenHash: item.token_hash,
    rotationEpoch: item.rotation_epoch,
    decoyType: item.decoy_type,
    sourcePath: item.source_path,
    status: item.status,
    issuedAt: item.issued_at,
    lastSeenAt: item.last_seen_at,
    revokedAt: item.revoked_at,
    revokeReason: item.revoke_reason,
  };
}

export function mapCanaryAssignmentSummary(
  data: BackendCanaryAssignmentSummary,
): CanaryAssignmentSummary {
  return {
    totalAssignments: data.total_assignments,
    assignments: data.assignments.map(mapCanaryAssignment),
  };
}

export function mapActorProfileSummary(
  data: BackendActorProfileSummary,
): ActorProfileSummary {
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

export function mapActorClusterSummary(
  data: BackendActorClusterSummary,
): ActorClusterSummary {
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

export function mapActorCaseSummary(
  data: BackendActorCaseSummary,
): ActorCaseSummary {
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

export function mapActorCaseWorkflow(item: BackendActorCaseWorkflow): ActorCaseWorkflow {
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
    assignedTo: item.assigned_to,
    analystNote: item.analyst_note,
    openedAt: item.opened_at,
    updatedAt: item.updated_at,
    updatedBy: item.updated_by ?? null,
    lastSeen: item.last_seen,
  };
}

export function mapActorCaseWorkflowSummary(
  data: BackendActorCaseWorkflowSummary,
): ActorCaseWorkflowSummary {
  return {
    totalCases: data.total_cases,
    cases: data.cases.map(mapActorCaseWorkflow),
  };
}

export function mapDashboardSnapshot(
  data: BackendDashboardSnapshot,
): DashboardSnapshot {
  return {
    events: data.events.map(mapDashboardEvent),
    alerts: data.alerts.map(mapDashboardAlert),
    overview: mapOverview(data.metrics),
    traffic: data.traffic,
    riskHistory: data.risk_history.map(mapRiskHistoryPoint),
    decoyStatus: mapDecoyStatus(data.decoy_status),
    trainingSummary: mapTrainingSummary(data.training_summary),
    mlShadowStatus: mapMLShadowStatus(data.ml_shadow_status),
    mlShadowSummary: mapMLShadowSummary(data.ml_shadow_summary),
    mlPromotionReadiness: mapMLPromotionReadiness(data.ml_promotion_readiness),
    honeytokens: mapHoneytokenSummary(data.honeytokens),
    canaryAssignments: mapCanaryAssignmentSummary(data.canary_assignments),
    actorProfiles: mapActorProfileSummary(data.actor_profiles),
    actorClusters: mapActorClusterSummary(data.actor_clusters),
    actorCases: mapActorCaseSummary(data.actor_cases),
    actorCaseWorkflows: mapActorCaseWorkflowSummary(data.actor_case_workflows),
  };
}

export function mapRiskHistoryPoint(point: BackendRiskHistoryPoint): RiskHistoryPoint {
  return { timestamp: point.timestamp, riskScore: point.risk_score };
}

export function mapDecoyStatus(data: BackendDecoyStatus): DecoyStatusData {
  return {
    activeDecoys: data.active_decoys,
    fakeEndpoints: data.fake_endpoints,
    capturedInteractions: data.captured_interactions,
    lastDecoyTrigger: data.last_decoy_trigger,
  };
}
