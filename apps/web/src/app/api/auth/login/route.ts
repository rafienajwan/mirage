import { randomBytes } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import {
  createOperatorSession,
  isSameOriginRequest,
  OPERATOR_SESSION_COOKIE,
  OPERATOR_SESSION_MAX_AGE,
  type OperatorIdentity,
} from "@/lib/operator-auth";
import { loginClientKey, loginThrottle } from "@/lib/login-throttle";

const NOT_CONFIGURED = { detail: "Operator authentication is not configured" };

// Asks the gateway to check the credentials. Returns the operator, "invalid"
// for wrong credentials, or null when the gateway cannot answer.
async function verifyWithGateway(
  gatewayUrl: string,
  apiKey: string,
  username: string,
  password: string,
): Promise<OperatorIdentity | "invalid" | null> {
  try {
    const response = await fetch(
      `${gatewayUrl.replace(/\/$/, "")}/api/v1/operators/login`,
      {
        method: "POST",
        cache: "no-store",
        headers: { "X-Mirage-API-Key": apiKey, "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      },
    );
    if (response.status === 401) return "invalid";
    if (!response.ok) return null;
    const body = (await response.json()) as { username?: unknown; role?: unknown };
    if (typeof body.username !== "string") return null;
    if (body.role !== "analyst" && body.role !== "admin") return null;
    return { sub: body.username, role: body.role };
  } catch {
    return null;
  }
}

export async function POST(request: NextRequest) {
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  const sessionSecret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  if (!gatewayUrl || !apiKey || !sessionSecret) {
    return NextResponse.json(NOT_CONFIGURED, { status: 503 });
  }

  const origin = request.headers.get("origin");
  const forwardedProtocol = request.headers
    .get("x-forwarded-proto")
    ?.split(",", 1)[0]
    ?.trim();
  if (!isSameOriginRequest({
    origin,
    host: request.headers.get("host"),
    protocol: forwardedProtocol || request.nextUrl.protocol,
  })) {
    return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  }

  let username: unknown;
  let password: unknown;
  try {
    ({ username, password } = (await request.json()) as {
      username?: unknown;
      password?: unknown;
    });
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (
    typeof username !== "string" ||
    typeof password !== "string" ||
    username.length > 64 ||
    password.length > 256
  ) {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  const clientKey = loginClientKey(
    request.headers,
    process.env.MIRAGE_TRUST_PROXY_HEADERS === "true",
    username,
  );
  // Charged as a failure up front; refunded below once the gateway accepts.
  const throttle = loginThrottle.attempt(clientKey);
  if (!throttle.allowed) {
    return NextResponse.json(
      { detail: "Too many login attempts" },
      {
        status: 429,
        headers: { "Retry-After": String(throttle.retryAfterSeconds) },
      },
    );
  }

  const operator = await verifyWithGateway(gatewayUrl, apiKey, username, password);
  if (operator === "invalid") {
    return NextResponse.json({ detail: "Invalid credentials" }, { status: 401 });
  }
  if (operator === null) {
    return NextResponse.json(NOT_CONFIGURED, { status: 503 });
  }
  loginThrottle.recordSuccess(clientKey);

  try {
    const session = await createOperatorSession({
      secret: sessionSecret,
      now: Math.floor(Date.now() / 1000),
      nonce: randomBytes(18).toString("base64url"),
      operator,
    });
    const response = NextResponse.json({ username: operator.sub, role: operator.role });
    response.cookies.set(OPERATOR_SESSION_COOKIE, session, {
      httpOnly: true,
      maxAge: OPERATOR_SESSION_MAX_AGE,
      path: "/",
      sameSite: "strict",
      secure:
        process.env.MIRAGE_SECURE_COOKIES === undefined
          ? process.env.NODE_ENV === "production"
          : process.env.MIRAGE_SECURE_COOKIES === "true",
    });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return NextResponse.json(NOT_CONFIGURED, { status: 503 });
  }
}
