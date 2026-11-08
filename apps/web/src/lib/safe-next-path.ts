const FALLBACK = "/dashboard";

/**
 * Resolve a post-login `next` target against the app origin and keep it only
 * when it stays on that origin. Browsers treat `/\evil.com` like
 * `//evil.com`, so a prefix check is not enough.
 */
export function safeNextPath(target: string | null, origin: string): string {
  if (!target || !target.startsWith("/")) return FALLBACK;
  try {
    const base = new URL(origin);
    const resolved = new URL(target, base);
    if (resolved.origin !== base.origin) return FALLBACK;
    // "/.//evil.com" resolves to the pathname "//evil.com", which the router
    // would treat as a protocol-relative URL to another host.
    if (resolved.pathname.startsWith("//")) return FALLBACK;
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return FALLBACK;
  }
}
