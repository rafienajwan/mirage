import { NextRequest, NextResponse } from "next/server";

import {
  OPERATOR_SESSION_COOKIE,
  verifyOperatorSession,
} from "@/lib/operator-auth";

const PUBLIC_API_PATHS = new Set([
  "/api/auth/login",
  "/api/auth/logout",
]);

export async function proxy(request: NextRequest) {
  if (PUBLIC_API_PATHS.has(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const secret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  const session = request.cookies.get(OPERATOR_SESSION_COOKIE)?.value;
  const now = Math.floor(Date.now() / 1000);
  const authenticated =
    Boolean(secret && session) &&
    await verifyOperatorSession(session as string, secret as string, now);
  if (authenticated) {
    return NextResponse.next();
  }

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json(
      { detail: "Authentication required" },
      { status: 401, headers: { "Cache-Control": "no-store" } },
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
