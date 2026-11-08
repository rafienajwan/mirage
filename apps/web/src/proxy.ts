import { NextRequest, NextResponse } from "next/server";

import {
  OPERATOR_SESSION_COOKIE,
  verifyOperatorSession,
} from "@/lib/operator-auth";
import { decideProxyAccess } from "@/lib/proxy-policy";

async function isAuthenticated(request: NextRequest) {
  const secret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  const session = request.cookies.get(OPERATOR_SESSION_COOKIE)?.value;
  if (!secret || !session) return false;
  return verifyOperatorSession(session, secret, Math.floor(Date.now() / 1000));
}

export async function proxy(request: NextRequest) {
  const decision = decideProxyAccess({
    method: request.method,
    pathname: request.nextUrl.pathname,
    origin: request.headers.get("origin"),
    host: request.headers.get("host"),
    forwardedProto: request.headers.get("x-forwarded-proto"),
    protocol: request.nextUrl.protocol,
    authenticated: await isAuthenticated(request),
  });

  if (decision === "allow") return NextResponse.next();

  if (decision === "unauthorized") {
    return NextResponse.json(
      { detail: "Authentication required" },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }

  if (decision === "forbidden") {
    return NextResponse.json(
      { detail: "Invalid request origin" },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set(
    "next",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  const response = NextResponse.redirect(loginUrl);
  response.cookies.delete(OPERATOR_SESSION_COOKIE);
  return response;
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/:path*"],
};
