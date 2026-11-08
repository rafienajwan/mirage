import { NextRequest, NextResponse } from "next/server";

import { gatewayTargetPath, isAllowedBridgeRequest } from "@/lib/gateway-bridge";

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
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Gateway bridge is not configured" },
      { status: 503, headers: NO_STORE },
    );
  }

  const target = new URL(gatewayTargetPath(path), `${gatewayUrl.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;

  const headers: Record<string, string> = { "X-Mirage-API-Key": apiKey };
  let body: string | undefined;
  if (request.method !== "GET") {
    body = await request.text();
    const contentType = request.headers.get("content-type");
    if (contentType) headers["Content-Type"] = contentType;
  }

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
