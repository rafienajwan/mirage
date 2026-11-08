// In-memory throttle for operator login attempts (single dashboard instance).
// A per-client limit slows one guesser; a global limit slows distributed
// guessing, at the cost of briefly locking everyone out during an attack.

export interface LoginThrottleOptions {
  perClientLimit?: number;
  globalLimit?: number;
  windowMs?: number;
  maxClients?: number;
  now?: () => number;
}

export interface ThrottleDecision {
  allowed: boolean;
  retryAfterSeconds: number;
}

export interface LoginThrottle {
  check(key: string): ThrottleDecision;
  // Check and, if allowed, count the attempt as a failure in one synchronous
  // step, so concurrent requests cannot all pass before any is recorded.
  // Call recordSuccess when the password turns out to be right.
  attempt(key: string): ThrottleDecision;
  recordFailure(key: string): void;
  recordSuccess(key: string): void;
}

export function createLoginThrottle({
  perClientLimit = 5,
  globalLimit = 50,
  windowMs = 15 * 60_000,
  maxClients = 10_000,
  now = Date.now,
}: LoginThrottleOptions = {}): LoginThrottle {
  // Map insertion order doubles as least-recently-failed order for eviction.
  const clients = new Map<string, number[]>();
  let global: number[] = [];

  const recent = (failures: number[], at: number) =>
    failures.filter((time) => time > at - windowMs);

  // A limit stays exceeded until the oldest failure that still counts toward
  // it leaves the window.
  const blockedUntil = (failures: number[], limit: number) =>
    failures.length >= limit ? failures[failures.length - limit] + windowMs : 0;

  const throttle: LoginThrottle = {
    attempt(key) {
      const decision = throttle.check(key);
      if (decision.allowed) throttle.recordFailure(key);
      return decision;
    },

    check(key) {
      const at = now();
      global = recent(global, at);
      const failures = recent(clients.get(key) ?? [], at);
      const until = Math.max(
        blockedUntil(failures, perClientLimit),
        blockedUntil(global, globalLimit),
      );
      if (until > at) {
        return {
          allowed: false,
          retryAfterSeconds: Math.max(1, Math.ceil((until - at) / 1000)),
        };
      }
      return { allowed: true, retryAfterSeconds: 0 };
    },

    recordFailure(key) {
      const at = now();
      const failures = recent(clients.get(key) ?? [], at);
      failures.push(at);
      clients.delete(key);
      clients.set(key, failures.slice(-perClientLimit));
      while (clients.size > maxClients) {
        const oldest = clients.keys().next().value;
        if (oldest === undefined) break;
        clients.delete(oldest);
      }
      global = recent(global, at);
      global.push(at);
      global = global.slice(-globalLimit);
    },

    recordSuccess(key) {
      // Undo the attempt this success was charged as.
      if (clients.has(key)) global.pop();
      clients.delete(key);
    },
  };
  return throttle;
}

// Next.js route handlers expose no socket address, so forwarded headers are
// honored only when a trusted reverse proxy sets them. That proxy appends the
// address it saw; everything to its left was written by the client.
export function loginClientKey(headers: Headers, trustProxyHeaders: boolean): string {
  if (!trustProxyHeaders) return "direct";
  const hops = headers.get("x-forwarded-for")?.split(",") ?? [];
  return hops[hops.length - 1]?.trim() || "direct";
}

export const loginThrottle = createLoginThrottle();
