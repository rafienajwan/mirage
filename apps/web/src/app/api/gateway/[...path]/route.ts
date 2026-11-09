import { NextRequest, NextResponse } from "next/server";

import {
  bridgeHeaders,
  gatewayTargetPath,
  isAllowedBridgeRequest,
} from "@/lib/gateway-bridge";
import { OPERATOR_SESSION_COOKIE, readOperatorSession } from "@/lib/operator-auth";

type BridgeContext = { params: Promise<{ path: string[] }> };

const NO_STORE = { "Cache-Control": "no-store" };

async function forward(request: NextRequest, context: BridgeContext) {
  const { path } = await context.params;
  if (!isAllowedBridgeRequest(request.method, path)) {
    return NextResponse.json(
      { detail: "Not found" },
      { status: 404, headers: NO_STORE },
    );
  }

  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  const sessionSecret = process.env.MIRAGE_OPERATOR_SESSION_SECRET;
  if (!gatewayUrl || !apiKey || !sessionSecret) {
    return NextResponse.json(
      { detail: "Gateway bridge is not configured" },
      { status: 503, headers: NO_STORE },
    );
  }

  const session = request.cookies.get(OPERATOR_SESSION_COOKIE)?.value;
  const operator = session
    ? await readOperatorSession(session, sessionSecret, Math.floor(Date.now() / 1000))
    : null;
  if (!operator) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: NO_STORE },
    );
  }

  const target = new URL(gatewayTargetPath(path), `${gatewayUrl.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;

  const isRead = request.method === "GET";
  const body = isRead ? undefined : await request.text();
  const headers = bridgeHeaders({
    apiKey,
    operator: operator.sub,
    contentType: isRead ? null : request.headers.get("content-type"),
  });

  try {
    const response = await fetch(target, {
      method: request.method,
      cache: "no-store",
      headers,
      body,
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        ...NO_STORE,
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Gateway is unavailable" },
      { status: 502, headers: NO_STORE },
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
