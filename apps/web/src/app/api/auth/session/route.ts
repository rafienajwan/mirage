import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { OPERATOR_SESSION_COOKIE, readOperatorSession } from "@/lib/operator-auth";

const NO_STORE = { "Cache-Control": "no-store" };

export async function GET() {
  const sessionSecret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  const session = (await cookies()).get(OPERATOR_SESSION_COOKIE)?.value;
  const operator =
    sessionSecret && session
      ? await readOperatorSession(session, sessionSecret, Math.floor(Date.now() / 1000))
      : null;
  if (!operator) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: NO_STORE },
    );
  }
  return NextResponse.json(
    { username: operator.sub, role: operator.role },
    { headers: NO_STORE },
  );
}
