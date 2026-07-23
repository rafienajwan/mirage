import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const gatewayUrl = process.env.MIRAGE_INTERNAL_API_URL;
  const apiKey = process.env.MIRAGE_API_KEY;
  if (!gatewayUrl || !apiKey) {
    return NextResponse.json(
      { detail: "Gateway bridge is not configured" },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const target = new URL(
    `/api/v1/${path.map(encodeURIComponent).join("/")}`,
    `${gatewayUrl.replace(/\/$/, "")}/`,
  );
  target.search = request.nextUrl.search;

  try {
    const response = await fetch(target, {
      cache: "no-store",
      headers: { "X-Mirage-API-Key": apiKey },
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Gateway is unavailable" },
      { status: 502 },
    );
  }
}
