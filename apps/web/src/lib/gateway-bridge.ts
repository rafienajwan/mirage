/**
 * Routing rules for the server-side gateway bridge (/api/gateway/[...path]).
 * Reads are forwarded for any well-formed path; writes only for the exact
 * operator actions the dashboard performs.
 */

const ID = "*";

const WRITE_ROUTES: ReadonlyArray<{ method: string; pattern: string[] }> = [
  { method: "PATCH", pattern: ["dashboard", "events", ID, "label"] },
  { method: "PATCH", pattern: ["dashboard", "actor-case-workflows", ID] },
  { method: "POST", pattern: ["dashboard", "canary-assignments", ID, "revoke"] },
  { method: "POST", pattern: ["dashboard", "actor-cases", ID, "open"] },
  { method: "POST", pattern: ["simulate", "normal"] },
  { method: "POST", pattern: ["simulate", "suspicious"] },
  { method: "POST", pattern: ["dashboard", "training-data", "retrain"] },
];

function isSafeSegment(segment: string) {
  return segment !== "" && segment !== "." && segment !== "..";
}

export function isAllowedBridgeRequest(method: string, segments: string[]): boolean {
  if (segments.length === 0 || !segments.every(isSafeSegment)) return false;
  const verb = method.toUpperCase();
  // The operator roster is readable; login and the audit log are not bridged.
  if (verb === "GET") return segments[0] !== "operators" || segments.length === 1;
  return WRITE_ROUTES.some(
    (route) =>
      route.method === verb &&
      route.pattern.length === segments.length &&
      route.pattern.every((part, i) => part === ID || part === segments[i]),
  );
}

// Outgoing headers are built from scratch so nothing the browser sent, such as
// its own X-Mirage-Operator, reaches the gateway.
export function bridgeHeaders({
  apiKey,
  operator,
  contentType,
}: {
  apiKey: string;
  operator: string;
  contentType: string | null;
}): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Mirage-API-Key": apiKey,
    "X-Mirage-Operator": operator,
  };
  if (contentType) headers["Content-Type"] = contentType;
  return headers;
}

export function gatewayTargetPath(segments: string[]): string {
  return `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
}
