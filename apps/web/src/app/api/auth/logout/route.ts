import { NextResponse } from "next/server";

import { OPERATOR_SESSION_COOKIE } from "@/lib/operator-auth";

export async function POST() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(OPERATOR_SESSION_COOKIE, "", {
    expires: new Date(0),
    httpOnly: true,
    path: "/",
    sameSite: "strict",
    secure:
      process.env.MIRAGE_SECURE_COOKIES === undefined
        ? process.env.NODE_ENV === "production"
        : process.env.MIRAGE_SECURE_COOKIES === "true",
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
