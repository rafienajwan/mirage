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

/**
 * Collapse a batch of settled dashboard requests into one error, or null when
 * all succeeded. An expired session wins so the caller can redirect.
 */
export function summarizeFailures(
  results: ReadonlyArray<PromiseSettledResult<unknown>>,
): unknown {
  const reasons = results.flatMap((result) =>
    result.status === "rejected" ? [result.reason] : [],
  );
  if (reasons.length === 0) return null;
  const expired = reasons.find((reason) => reason instanceof SessionExpiredError);
  if (expired) return expired;
  const first = reasons[0] instanceof Error ? reasons[0].message : "Request failed";
  return new Error(
    `${reasons.length} of ${results.length} dashboard requests failed. ${first}`,
  );
}
