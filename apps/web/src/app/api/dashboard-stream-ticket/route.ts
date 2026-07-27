import { randomBytes } from "node:crypto";

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  createDashboardStreamTicket,
  OPERATOR_SESSION_COOKIE,
  verifyOperatorSession,
} from "@/lib/operator-auth";

export async function GET() {
  const sessionSecret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  const ticketSecret = process.env.MIRAGE_DASHBOARD_TICKET_SECRET;
  const streamUrl = process.env.MIRAGE_DASHBOARD_WS_URL;
  if (!sessionSecret || !ticketSecret || !streamUrl) {
    return NextResponse.json(
      { detail: "Dashboard stream is not configured" },
      { status: 503 },
    );
  }

  const session = (await cookies()).get(OPERATOR_SESSION_COOKIE)?.value;
  const now = Math.floor(Date.now() / 1000);
  if (!session || !(await verifyOperatorSession(session, sessionSecret, now))) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(streamUrl);
  } catch {
    return NextResponse.json(
      { detail: "Dashboard stream is not configured" },
      { status: 503 },
    );
  }
  if (!["ws:", "wss:"].includes(parsedUrl.protocol)) {
    return NextResponse.json(
      { detail: "Dashboard stream is not configured" },
      { status: 503 },
    );
  }

  try {
    const ticket = await createDashboardStreamTicket({
      secret: ticketSecret,
      now,
      nonce: randomBytes(18).toString("base64url"),
    });
    return NextResponse.json(
      { url: parsedUrl.toString(), ...ticket },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { detail: "Dashboard stream is not configured" },
      { status: 503 },
    );
  }
}
