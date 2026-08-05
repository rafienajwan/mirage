import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import {
  createOperatorSession,
  isSameOriginRequest,
  OPERATOR_SESSION_COOKIE,
  OPERATOR_SESSION_MAX_AGE,
} from "@/lib/operator-auth";

function passwordMatches(candidate: string, expected: string) {
  const candidateDigest = createHash("sha256").update(candidate).digest();
  const expectedDigest = createHash("sha256").update(expected).digest();
  return timingSafeEqual(candidateDigest, expectedDigest);
}

export async function POST(request: NextRequest) {
  const password = process.env.MIRAGE_OPERATOR_PASSWORD;
  const sessionSecret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  if (!password || password.length < 16 || !sessionSecret) {
    return NextResponse.json(
      { detail: "Operator authentication is not configured" },
      { status: 503 },
    );
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

  let candidate: unknown;
  try {
    candidate = (await request.json() as { password?: unknown }).password;
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (typeof candidate !== "string" || !passwordMatches(candidate, password)) {
    return NextResponse.json({ detail: "Invalid credentials" }, { status: 401 });
  }

  try {
    const now = Math.floor(Date.now() / 1000);
    const session = await createOperatorSession({
      secret: sessionSecret,
      now,
      nonce: randomBytes(18).toString("base64url"),
    });
    const response = NextResponse.json({ authenticated: true });
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
    return NextResponse.json(
      { detail: "Operator authentication is not configured" },
      { status: 503 },
    );
  }
}
