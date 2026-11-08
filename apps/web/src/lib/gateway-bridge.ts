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
  if (verb === "GET") return true;
  return WRITE_ROUTES.some(
    (route) =>
      route.method === verb &&
      route.pattern.length === segments.length &&
      route.pattern.every((part, i) => part === ID || part === segments[i]),
  );
}

export function gatewayTargetPath(segments: string[]): string {
  return `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
}
