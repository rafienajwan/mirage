/**
 * Shared types for Project MIRAGE dashboard.
 * These types are used across components and in the API client.
 */

// ─── Threat activity feed types ────────────────────────────────
export type ThreatSeverity = "low" | "medium" | "high" | "critical";
export type ThreatStatus = "allowed" | "redirected" | "decoy_active" | "contained" | "alert";

// ─── Alerts panel types ────────────────────────────────────────
export type AlertSeverity = "info" | "warning" | "critical";
