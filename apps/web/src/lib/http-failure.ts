/**
 * Turn a failed /api response into something an operator can act on.
 * 401 means the operator session expired (the proxy rejected the cookie).
 */
export function describeHttpFailure(
  status: number,
  body: string,
): { sessionExpired: boolean; message: string } {
  let detail: string | null = null;
  try {
    const parsed: unknown = JSON.parse(body);
    const raw = (parsed as { detail?: unknown } | null)?.detail;
    if (typeof raw === "string") {
      detail = raw;
    } else if (Array.isArray(raw) && typeof raw[0]?.msg === "string") {
      detail = raw[0].msg;
    }
  } catch {
    detail = null;
  }
  return {
    sessionExpired: status === 401,
    message: `${detail ?? "Request failed"} (HTTP ${status})`,
  };
}

/** Thrown by the fetchers when the operator session is no longer valid. */
export class SessionExpiredError extends Error {
  constructor() {
    super("Your operator session has expired. Sign in again.");
    this.name = "SessionExpiredError";
  }
}
