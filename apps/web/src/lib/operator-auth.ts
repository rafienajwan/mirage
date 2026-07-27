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

interface CreateTokenOptions {
  secret: string;
  now: number;
  nonce: string;
}

interface StreamTicket {
  token: string;
  expiresAt: number;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

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
  claims: SignedClaims,
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
): Promise<boolean> {
  if (secret.length < 32 || !Number.isInteger(now) || now < 0) return false;
  const segments = token.split(".");
  if (segments.length !== 2) return false;

  try {
    const [payloadSegment, signatureSegment] = segments;
    const validSignature = await crypto.subtle.verify(
      "HMAC",
      await importHmacKey(secret),
      decodeBase64Url(signatureSegment),
      encoder.encode(payloadSegment),
    );
    if (!validSignature) return false;

    const claims = JSON.parse(
      decoder.decode(decodeBase64Url(payloadSegment)),
    ) as Partial<SignedClaims>;
    if (
      claims.aud !== audience ||
      !Number.isInteger(claims.iat) ||
      !Number.isInteger(claims.exp) ||
      typeof claims.nonce !== "string" ||
      claims.nonce.length < 16
    ) {
      return false;
    }

    const issuedAt = claims.iat as number;
    const expiresAt = claims.exp as number;
    return (
      issuedAt - CLOCK_SKEW_SECONDS <= now &&
      now < expiresAt &&
      expiresAt > issuedAt &&
      expiresAt - issuedAt <= maximumLifetime
    );
  } catch {
    return false;
  }
}

export async function createOperatorSession({
  secret,
  now,
  nonce,
}: CreateTokenOptions): Promise<string> {
  assertTokenInput(now, nonce);
  return createSignedToken(
    {
      aud: OPERATOR_SESSION_AUDIENCE,
      iat: now,
      exp: now + OPERATOR_SESSION_TTL_SECONDS,
      nonce,
    },
    secret,
  );
}

export function verifyOperatorSession(
  token: string,
  secret: string,
  now: number,
): Promise<boolean> {
  return verifySignedToken(token, secret, {
    audience: OPERATOR_SESSION_AUDIENCE,
    now,
    maximumLifetime: OPERATOR_SESSION_TTL_SECONDS,
  });
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

export function verifyDashboardStreamTicket(
  token: string,
  secret: string,
  now: number,
): Promise<boolean> {
  return verifySignedToken(token, secret, {
    audience: DASHBOARD_STREAM_AUDIENCE,
    now,
    maximumLifetime: 120,
  });
}
