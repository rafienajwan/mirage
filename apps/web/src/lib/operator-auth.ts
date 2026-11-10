const OPERATOR_SESSION_AUDIENCE = "mirage-operator-session";
const DASHBOARD_STREAM_AUDIENCE = "mirage-dashboard-stream";
const OPERATOR_SESSION_TTL_SECONDS = 8 * 60 * 60;
const DASHBOARD_STREAM_TTL_SECONDS = 60;
const CLOCK_SKEW_SECONDS = 5;

export const OPERATOR_SESSION_COOKIE = "mirage_operator_session";
export const OPERATOR_SESSION_MAX_AGE = OPERATOR_SESSION_TTL_SECONDS;

interface SignedClaims {
  aud: string;
  exp: number;
  iat: number;
  nonce: string;
}

const OPERATOR_USERNAME = /^[a-z0-9][a-z0-9._-]{1,31}$/;
const OPERATOR_ROLES = new Set(["analyst", "admin"]);

export type OperatorRole = "analyst" | "admin";

export interface OperatorIdentity {
  sub: string;
  role: OperatorRole;
}

interface CreateTokenOptions {
  secret: string;
  now: number;
  nonce: string;
}

interface StreamTicket {
  token: string;
  expiresAt: number;
}

interface SameOriginOptions {
  origin: string | null;
  host: string | null;
  protocol: string;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export function isSameOriginRequest({
  origin,
  host,
  protocol,
}: SameOriginOptions): boolean {
  if (!origin) return true;
  if (!host) return false;

  const normalizedProtocol = protocol.endsWith(":")
    ? protocol
    : `${protocol}:`;
  try {
    return new URL(origin).origin === `${normalizedProtocol}//${host}`;
  } catch {
    return false;
  }
}

function assertSecret(secret: string) {
  if (secret.length < 32) {
    throw new Error("Authentication secret must contain at least 32 characters");
  }
}

function assertTokenInput(now: number, nonce: string) {
  if (!Number.isInteger(now) || now < 0) {
    throw new Error("Token issue time must be a non-negative integer");
  }
  if (nonce.length < 16) {
    throw new Error("Token nonce must contain at least 16 characters");
  }
}

function encodeBase64Url(value: Uint8Array) {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(normalized + padding);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function importHmacKey(secret: string) {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function createSignedToken(
  claims: SignedClaims & Record<string, unknown>,
  secret: string,
): Promise<string> {
  assertSecret(secret);
  const payload = encodeBase64Url(
    encoder.encode(JSON.stringify(claims)),
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    await importHmacKey(secret),
    encoder.encode(payload),
  );
  return `${payload}.${encodeBase64Url(new Uint8Array(signature))}`;
}

async function verifySignedToken(
  token: string,
  secret: string,
  {
    audience,
    now,
    maximumLifetime,
  }: {
    audience: string;
    now: number;
    maximumLifetime: number;
  },
): Promise<Record<string, unknown> | null> {
  if (secret.length < 32 || !Number.isInteger(now) || now < 0) return null;
  const segments = token.split(".");
  if (segments.length !== 2) return null;

  try {
    const [payloadSegment, signatureSegment] = segments;
    const validSignature = await crypto.subtle.verify(
      "HMAC",
      await importHmacKey(secret),
      decodeBase64Url(signatureSegment),
      encoder.encode(payloadSegment),
    );
    if (!validSignature) return null;

    const claims = JSON.parse(
      decoder.decode(decodeBase64Url(payloadSegment)),
    ) as Partial<SignedClaims> & Record<string, unknown>;
    if (
      claims.aud !== audience ||
      !Number.isInteger(claims.iat) ||
      !Number.isInteger(claims.exp) ||
      typeof claims.nonce !== "string" ||
      claims.nonce.length < 16
    ) {
      return null;
    }

    const issuedAt = claims.iat as number;
    const expiresAt = claims.exp as number;
    const current =
      issuedAt - CLOCK_SKEW_SECONDS <= now &&
      now < expiresAt &&
      expiresAt > issuedAt &&
      expiresAt - issuedAt <= maximumLifetime;
    return current ? claims : null;
  } catch {
    return null;
  }
}

function isOperatorIdentity(value: { sub?: unknown; role?: unknown }): value is OperatorIdentity {
  return (
    typeof value.sub === "string" &&
    OPERATOR_USERNAME.test(value.sub) &&
    typeof value.role === "string" &&
    OPERATOR_ROLES.has(value.role)
  );
}

export async function createOperatorSession({
  secret,
  now,
  nonce,
  operator,
}: CreateTokenOptions & { operator: OperatorIdentity }): Promise<string> {
  assertTokenInput(now, nonce);
  if (!isOperatorIdentity(operator)) {
    throw new Error("Operator session needs a valid username and role");
  }
  return createSignedToken(
    {
      aud: OPERATOR_SESSION_AUDIENCE,
      iat: now,
      exp: now + OPERATOR_SESSION_TTL_SECONDS,
      nonce,
      sub: operator.sub,
      role: operator.role,
    },
    secret,
  );
}

// The operator a session names, or null when the session is invalid, expired,
// or predates operator accounts.
export async function readOperatorSession(
  token: string,
  secret: string,
  now: number,
): Promise<OperatorIdentity | null> {
  const claims = await verifySignedToken(token, secret, {
    audience: OPERATOR_SESSION_AUDIENCE,
    now,
    maximumLifetime: OPERATOR_SESSION_TTL_SECONDS,
  });
  if (!claims || !isOperatorIdentity(claims)) return null;
  return { sub: claims.sub, role: claims.role };
}

export async function verifyOperatorSession(
  token: string,
  secret: string,
  now: number,
): Promise<boolean> {
  return (await readOperatorSession(token, secret, now)) !== null;
}

export async function createDashboardStreamTicket({
  secret,
  now,
  nonce,
}: CreateTokenOptions): Promise<StreamTicket> {
  assertTokenInput(now, nonce);
  const expiresAt = now + DASHBOARD_STREAM_TTL_SECONDS;
  return {
    token: await createSignedToken(
      {
        aud: DASHBOARD_STREAM_AUDIENCE,
        iat: now,
        exp: expiresAt,
        nonce,
      },
      secret,
    ),
    expiresAt,
  };
}
