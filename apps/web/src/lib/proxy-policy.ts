import { isSameOriginRequest } from "./operator-auth";

export interface ProxyRequestFacts {
  method: string;
  pathname: string;
  origin: string | null;
  host: string | null;
  forwardedProto: string | null;
  protocol: string;
  authenticated: boolean;
}

export type ProxyDecision = "allow" | "unauthorized" | "forbidden" | "login";

const PUBLIC_API_PATHS = new Set(["/api/auth/login", "/api/auth/logout"]);
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * Access policy for /dashboard and /api. State-changing API calls must carry
 * a same-origin Origin header: the session cookie alone is not proof that the
 * operator's own page sent the request.
 */
export function decideProxyAccess(request: ProxyRequestFacts): ProxyDecision {
  if (PUBLIC_API_PATHS.has(request.pathname)) return "allow";

  const isApi = request.pathname.startsWith("/api/");
  if (!request.authenticated) return isApi ? "unauthorized" : "login";

  if (isApi && !SAFE_METHODS.has(request.method.toUpperCase())) {
    const protocol =
      request.forwardedProto?.split(",", 1)[0]?.trim() || request.protocol;
    if (
      !request.origin ||
      !isSameOriginRequest({
        origin: request.origin,
        host: request.host,
        protocol,
      })
    ) {
      return "forbidden";
    }
  }
  return "allow";
}
